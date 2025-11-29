import boto3
import json
import time
from config import Config
from database.analytics_db import save_search_analytics


def process_search_event(event):
    try:
        print(f"Processing: {event['query']} "
              f"(results: {event['results_count']}, "
              f"cached: {event['cached']})")
        
        save_search_analytics(
            event['query'],
            event['results_count'],
            event['cached']
        )
        
        print(f"Saved to DB")
        
    except Exception as e:
        print(f"Error: {e}")


def start_worker():
    print("=" * 50)
    print("SQS Analytics Worker")
    print("=" * 50)
    print("\nConnecting to Amazon SQS...")
    

    sqs = boto3.client('sqs', region_name=Config.AWS_REGION)
    queue_url = Config.SQS_QUEUE_URL
    
    print(f"Connected!")
    print(f"Listening to queue: {queue_url}")
    print("\nWaiting for messages... (Ctrl+C to stop)\n")
    
    try:
        while True:
            response = sqs.receive_message(
                QueueUrl=queue_url,
                MaxNumberOfMessages=10,
                WaitTimeSeconds=20,  # Long polling
                VisibilityTimeout=30
            )
            
            if 'Messages' not in response:
                continue
            
            for message in response['Messages']:
                try:
                    event = json.loads(message['Body'])
                    
                    # Process event
                    process_search_event(event)
                    

                    sqs.delete_message(
                        QueueUrl=queue_url,
                        ReceiptHandle=message['ReceiptHandle']
                    )
                    
                except Exception as e:
                    print(f"Message processing error: {e}")
                    
                    
    except KeyboardInterrupt:
        print("\n\nStopping worker...")
        print("Worker stopped")


if __name__ == '__main__':
    start_worker()