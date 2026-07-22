import json
import os
import boto3
import re
import urllib.parse
from datetime import datetime

def lambda_handler(event, context):
    stepfunctions_client = boto3.client('stepfunctions')
    
    file_key = urllib.parse.unquote_plus(event['Records'][0]['s3']['object']['key'])
    file_name = file_key.split('/')[-1]
    
    # TODO: adjust accordingly
    datasets_bucket = "datasets-zengrit" 
    models_bucket = "models-zengrit"
    
    # Build the required S3 URIs
    s3_input_uri = f"s3://{datasets_bucket}/raw/{file_name}"         # Raw input file URI
    s3_processed_uri = f"s3://{datasets_bucket}/processed/"          # Processed data output folder
    s3_test_uri = f"s3://{datasets_bucket}/test/"                    # Test data folder
    s3_staging_uri = f"s3://{models_bucket}/staging/"
    
    # Generate a unique job ID
    timestamp = datetime.utcnow().strftime('%Y%m%d%H%M%S')
    sanitized_name = file_name.replace('.', '-').replace('_', '-')
    unique_job_id = f"{sanitized_name}-{timestamp}"

    # Create the payload to pass to Step Functions
    payload = {
        "id": unique_job_id,
        "s3InputUri": s3_input_uri,
        "s3ProcessedOutputUri": s3_processed_uri,
        "s3TestDataUri": s3_test_uri,
        "s3StagingUri": s3_staging_uri,
        "fileName": file_name
    }
    
    # WARNING: Do not hardcode the real ARN here -- this file is public.
    # Set AWS_STATE_MACHINE_ARN in the Lambda's environment variables
    # instead.
    state_machine_arn = os.environ["AWS_STATE_MACHINE_ARN"]
    print(f"Constructed Payload: {json.dumps(payload)}")
    print(f"Triggering State Machine: {state_machine_arn}")
    
    response = stepfunctions_client.start_execution(
        stateMachineArn=state_machine_arn,
        input=json.dumps(payload)
    )
    
    return {
        'statusCode': 200,
        'body': json.dumps(response, default=str)
    }
