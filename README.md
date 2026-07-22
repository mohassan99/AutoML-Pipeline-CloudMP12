# AutoML Pipeline — AWS Step Functions + SageMaker

An automated machine learning pipeline built on AWS that detects concept drift in incoming data, retrains a classification model when drift is detected, evaluates the challenger model against the production champion using F1 score, and deploys a new endpoint only when the challenger outperforms the current model. The entire workflow is event-driven and fully automated — uploading a dataset to S3 triggers the pipeline end to end.

---

## Why this pattern matters

Concept drift — when live data shifts away from what a model was trained on — silently degrades production models with no error thrown and no alert fired. This pipeline automates the full response loop: detect drift, retrain, evaluate challenger vs. champion on F1, deploy only if performance improves. No manual intervention, no stale models serving quietly degraded predictions.

The same event-driven retraining architecture applies across the highest-demand ML domains:

| Healthcare Payers | Health Systems | Insurance & Fintech | Manufacturing & Retail |
|---|---|---|---|
| Member risk stratification | Sepsis / deterioration prediction | P&C claims fraud detection | Predictive maintenance |
| Prior auth triage | Readmission risk | Underwriting / loss ratio | Quality control defect detection |
| Claims fraud / waste / abuse | Revenue cycle denial prediction | Transaction fraud detection | Demand forecasting |
| Stars / HEDIS measure modeling | Prior auth approval likelihood | Credit risk / AML | Customer churn modeling |
| Rising risk identification | Clinical decision support | Algorithmic decisioning | Dynamic pricing |

Swap the dataset and model class — the orchestration layer is identical.

---

## Architecture

```
S3 Upload (raw/)
    └─► Lambda Trigger
            └─► AWS Step Functions State Machine
                    ├─► PreprocessingAndDriftCheck  (SageMaker Processing)
                    ├─► Get Drift Data              (Lambda)
                    ├─► DriftChoice
                    │       ├─ [drift detected]
                    │       │       ├─► Model Training      (SageMaker Training)
                    │       │       ├─► Model Evaluation    (SageMaker Processing)
                    │       │       ├─► Get F1 Scores       (Lambda)
                    │       │       └─► F1Choice
                    │       │               ├─ [challenger > champion] ──► Deploy Model and Endpoint (Lambda)
                    │       │               └─ [default] ──────────────► Retain Model
                    │       └─ [no drift] ──────────────────────────────► Retain Model
```

---

## AWS Services

- **AWS Step Functions** — orchestrates the full pipeline as a state machine
- **AWS SageMaker Processing** — runs preprocessing/drift detection and model evaluation jobs
- **AWS SageMaker Training** — trains the XGBoost classifier
- **AWS SageMaker Endpoint** — serves the production model for inference
- **AWS Lambda** — event trigger, drift result reader, F1 score reader, model deployment
- **Amazon S3** — stores raw data, processed data, model artifacts, and evaluation results

---

## Pipeline Components

### `drift_preproc.py` — Preprocessing and Drift Detection

Runs as a SageMaker Processing job. Downloads the new raw dataset, splits it into train/test sets, and compares the production model's F1 score on historical test data versus combined historical + new data. If performance drops more than 10 percentage points, drift is flagged. On the first run with no production model, drift is forced to trigger initial training. Writes `drift_result.json` and updated preprocessor artifacts (`imputer.pkl`, `scaler.pkl`) to S3 staging.

### `train.py` — Model Training

Runs as a SageMaker Training job. Trains an XGBoost binary classifier on the preprocessed fraud detection dataset. If a production model exists, warm-starts training from it. Bundles the trained model, preprocessor artifacts, and inference script into a `model.tar.gz` artifact for deployment.

### `evaluate.py` — Champion vs. Challenger Evaluation

Runs as a SageMaker Processing job. Loads the newly trained challenger model and the current production champion model, evaluates both on the combined test set, and writes `evaluation.json` containing `champion_f1` and `challenger_f1` to S3 staging.

### `inference.py` — SageMaker Inference Handler

Implements the SageMaker serving interface (`model_fn`, `input_fn`, `predict_fn`, `output_fn`). Accepts JSON input, runs XGBoost prediction with a 0.5 threshold, and returns fraud probability and binary classification results.

### `utility.py` — Shared Utilities

Shared library used across all scripts. Provides S3 download/upload helpers, model tarball creation and extraction, fraud data preprocessing (feature engineering, imputation, scaling, one-hot encoding), local inference for drift scoring, and `get_production_model()` which retrieves the current champion from the SageMaker model registry.

### `lambdaTriggerStateMachine.py` — S3 Event Trigger

Lambda function triggered by S3 `ObjectCreated` events on the `raw/` prefix. Constructs all required S3 URIs and a unique job ID from the filename and timestamp, then starts the Step Functions execution with a structured payload.

### `get-f1-scores.py` — F1 Score Reader

Lambda function that reads `evaluation.json` from S3 staging and returns `champion_f1`, `challenger_f1`, and an `is_better` flag to the state machine.

### `deploy.py` — Model Deployment

Lambda function that creates or updates the SageMaker model, endpoint configuration, and endpoint. If the endpoint already exists it updates in place; otherwise it creates a new one.

---

## State Machine Configuration Files

| File | Description |
|---|---|
| `conf_preprocessing.json` | Arguments for the PreprocessingAndDriftCheck SageMaker Processing state |
| `conf_training.json` | Arguments for the Model Training SageMaker Training state |
| `conf_eval.json` | Arguments for the Model Evaluation SageMaker Processing state |

---

## Dataset

Credit card fraud detection dataset split into three test cases:

| Dataset | Purpose | Expected Pipeline Path |
|---|---|---|
| `base1_dataset.csv` | First run — no production model exists, forces drift | Full path → Deploy |
| `base2_dataset.csv` | Same distribution as base1 — no drift expected | Short path → Retain Model |
| `concept_drift_dataset.csv` | Significant distribution shift — drift expected | Full path → Deploy |

---

## Tech Stack

Python · XGBoost · scikit-learn · boto3 · AWS Step Functions · SageMaker · Lambda · S3 · IAM
