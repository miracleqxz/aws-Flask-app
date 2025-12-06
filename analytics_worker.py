#!/usr/bin/env python3
import sys
import time

sys.stdout = sys.stdout
sys.stderr = sys.stderr

print("=" * 50, flush=True)
print("Analytics Worker Starting...", flush=True)
print(f"Python: {sys.version}", flush=True)
print("=" * 50, flush=True)

time.sleep(1)

try:
    print("Importing modules...", flush=True)
    import boto3
    import json
    from config import Config
    from database.analytics_db import save_search_analytics
    print("Imports successful!", flush=True)
    
except Exception as e:
    print(f"IMPORT ERROR: {e}", flush=True)
    import traceback
    traceback.print_exc()
    sys.exit(1)


def process_search_event(event):
    try:
        print(f"Processing: query='{event['query']}' "
              f"results={event['results_count']} "
              f"cached={event['cached']}", flush=True)
        
        save_search_analytics(
            event['query'],
            event['results_count'],
            event['cached']
        )
        
        print(f"Saved to database", flush=True)
        
    except Exception as e:
        print(f"Processing error: {e}", flush=True)
        import traceback
        traceback.print_exc()


def start_worker():
    print("\n" + "=" * 50, flush=True)
    print("SQS Analytics Worker", flush=True)
    print("=" * 50, flush=True)
    
    try:
        print(f"\nConfiguration:", flush=True)
        print(f"  AWS Region: {Config.AWS_REGION}", flush=True)
        print(f"  SQS Queue: {Config.SQS_QUEUE_URL}", flush=True)
        print(f"  PostgreSQL: {Config.POSTGRES_HOST}:{Config.POSTGRES_PORT}", flush=True)
        print(f"  Database: {Config.POSTGRES_DB}", flush=True)
        
    except Exception as e:
        print(f"Config error: {e}", flush=True)
        sys.exit(1)
    
    try:
        print(f"Connecting to Amazon SQS...", flush=True)
        sqs = boto3.client('sqs', region_name=Config.AWS_REGION)
        
        response = sqs.get_queue_attributes(
            QueueUrl=Config.SQS_QUEUE_URL,
            AttributeNames=['ApproximateNumberOfMessages']
        )
        msg_count = response['Attributes']['ApproximateNumberOfMessages']
        
        print(f"Connected to SQS!", flush=True)
        print(f"Messages in queue: {msg_count}", flush=True)
        
    except Exception as e:
        print(f"SQS connection error: {e}", flush=True)
        import traceback
        traceback.print_exc()
        print("\nWorker cannot start without SQS connection", flush=True)
        print("   Check Security Groups and IAM permissions", flush=True)
        sys.exit(1)
    
    print(f"\nListening to queue...", flush=True)
    print(f"   (Ctrl+C to stop)\n", flush=True)
    
    message_count = 0
    error_count = 0
    
    try:
        while True:
            try:
                response = sqs.receive_message(
                    QueueUrl=Config.SQS_QUEUE_URL,
                    MaxNumberOfMessages=10,
                    WaitTimeSeconds=20,
                    VisibilityTimeout=30
                )
                
                if 'Messages' not in response:
                    print(".", end="", flush=True)  
                    continue
                
                print(f"\nReceived {len(response['Messages'])} message(s)", flush=True)
                
                for message in response['Messages']:
                    try:
                        event = json.loads(message['Body'])
                        
                        process_search_event(event)
                        message_count += 1
                        
                        sqs.delete_message(
                            QueueUrl=Config.SQS_QUEUE_URL,
                            ReceiptHandle=message['ReceiptHandle']
                        )
                        
                    except json.JSONDecodeError as e:
                        print(f"Invalid JSON in message: {e}", flush=True)
                        error_count += 1
                        
                    except Exception as e:
                        print(f"Message processing error: {e}", flush=True)
                        error_count += 1
                        import traceback
                        traceback.print_exc()
                
                
                if message_count % 10 == 0:
                    print(f"\nStats: processed={message_count}, errors={error_count}", flush=True)
                    
            except Exception as e:
                print(f"\nWorker loop error: {e}", flush=True)
                error_count += 1
                import traceback
                traceback.print_exc()
                time.sleep(5)  
                
    except KeyboardInterrupt:
        print(f"\n\nStopping worker...", flush=True)
        print(f"Final stats: processed={message_count}, errors={error_count}", flush=True)
        print("Worker stopped", flush=True)


if __name__ == '__main__':
    try:
        start_worker()
    except Exception as e:
        print(f"\nFATAL ERROR: {e}", flush=True)
        import traceback
        traceback.print_exc()
        sys.exit(1)