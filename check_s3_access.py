
def main():
    import os

    import boto3
    from dotenv import load_dotenv

    load_dotenv()

    region = os.environ["AWS_REGION"]
    bucket = os.environ["AWS_S3_BUCKET"]
    s3 = boto3.client("s3", region_name=region)

    # Uses the configured AWS credentials.
    response = s3.list_objects_v2(
        Bucket=bucket,
        MaxKeys=5,
    )

    print("S3 access successful.")
    print("Bucket:", bucket)
    print("Objects found:", len(response.get("Contents", [])))


if __name__ == "__main__":
    main()
