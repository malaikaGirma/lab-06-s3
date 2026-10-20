
import sys
import os
import time
import json
import logging
import requests
import boto3
from botocore.exceptions import ClientError

# Set up the logger to report status and errors
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# create 1 S3 client at module level
# all functions share this same client
s3 = boto3.client("s3", region_name="us-east-1")


# read 3 command-line arguments in this order: 1) Path to book_urls.txt, 2) Path to index.html, 3) the name of the bucket (public-mst3k)
# Return them as: (list_file, index_path, bucket)
def parse_args():
    if len(sys.argv) < 4: # <4 because arg[0] is file itself 
        logger.error(
            "Usage: python stage_books.py <book_urls.txt> "
            "<index.html> <bucket-name>"
        )
        sys.exit(1)

    return sys.argv[1], sys.argv[2], sys.argv[3]


# Download books from the URL list.
# arguments: list_file, dest_dir. return: list of local file paths.
def download_books(list_file, dest_dir):
    # create the destination folder (if it does not already exist)
    os.makedirs(dest_dir, exist_ok=True) #given code
    downloaded_files = [] #a list of the local paths of the books

    # read the URL list and skip blank lines.
    with open(list_file, "r") as file:
        urls = [line.strip() for line in file if line.strip()]

    for url in urls:
        # use the last part of the URL as the filename.
        filename = url.split("/")[-1]
        filepath = os.path.join(dest_dir, filename)

        # skip downloading if the file already exists.
        if os.path.exists(filepath):
            logger.info("Already downloaded: %s", filepath)
            downloaded_files.append(filepath)
            continue 

        # catch HTTP/network errors and log them
        try:
            response = requests.get(url, timeout=30) # in the lab instructions
            response.raise_for_status()  # detect HTTP errors like 404

            # save the downloaded content to the local file
            with open(filepath, "wb") as file:
                file.write(response.content)

            downloaded_files.append(filepath)
            logger.info("Downloaded: %s", filepath)

        except requests.RequestException as error:
            # Log the error and continue to the next book.
            logger.error("Failed to download %s: %s", url, error)

        # pause between URLs to avoid too many requests
        time.sleep(1)

    return downloaded_files


# check whether the bucket exists first
#  return t if it exists or is created successfully; if not f
def create_bucket(bucket):
    try:
        # check whether the bucket already exists and is accessible
        s3.head_bucket(Bucket=bucket)
        logger.info("Bucket already exists: %s", bucket)
        return True

    except ClientError as error:
        status = error.response.get(
            "ResponseMetadata", {}
        ).get("HTTPStatusCode")

        # If the error is not a 404, do not assume the bucket is absent
        if status != 404:
            logger.error("Cannot check bucket: %s", error)
            return False

    # create the bucket if the check returned 404.
    try:
        # this uses the us-east-1 region.
        s3.create_bucket(Bucket=bucket)
        logger.info("Created bucket: %s", bucket)
        return True

    except ClientError as error:
        logger.error("Failed to create bucket: %s", error)
        return False


# make the bucket publicly readable
# return t on success, f on failure
def make_public(bucket):
    try:
        # turn off Block Public Access for this bucket (given code from assignment)
        s3.put_public_access_block(
            Bucket=bucket,
            PublicAccessBlockConfiguration={
                "BlockPublicAcls": False,
                "IgnorePublicAcls": False,
                "BlockPublicPolicy": False,
                "RestrictPublicBuckets": False,
            },
        )

        # create a policy allowing anyone to read objects in this bucket. also code from assignment
        policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": "*",
                    "Action": "s3:GetObject",
                    # Use the bucket argument instead of a fixed name
                    "Resource": f"arn:aws:s3:::{bucket}/*",
                }
            ],
        }

        # attach the policy AFTER disabling Block Public Access.
        s3.put_bucket_policy(
            Bucket=bucket,
            Policy=json.dumps(policy),
        )

        logger.info("Bucket is publicly readable: %s", bucket)
        return True

    except ClientError as error:
        logger.error("Failed to make bucket public: %s", error)
        return False


# upload each downloaded book to the ROOT of the bucket
# Arguments: bucket, file_paths. Return: number of successfully uploaded files
def upload_files(bucket, file_paths):
    uploaded = 0

    for filepath in file_paths:
        try:
            s3.upload_file(
                filepath,
                bucket,
                # Use just the filename, not "books/filename".
                os.path.basename(filepath),
                # Tell browsers to display the object as plain text.
                ExtraArgs={"ContentType": "text/plain; charset=utf-8"},
            )

            logger.info("Uploaded: %s", filepath)
            uploaded += 1

        except ClientError as error:
            # log the failure but continue uploading other books.
            logger.error("Failed to upload %s: %s", filepath, error)

    return uploaded


# Upload the index page with the key "index.html".
# Arguments: bucket, index_path. Return t on success, f otherwise.
def upload_index(bucket, index_path):
    try:
        s3.upload_file(
            index_path,
            bucket,
            "index.html",
            # Tell browsers to display this object as a web page.
            ExtraArgs={"ContentType": "text/html"},
        )

        logger.info("Uploaded index.html")
        return True

    # Handle AWS errors and a missing/unreadable local file.
    except (ClientError, OSError) as error:
        logger.error("Failed to upload index.html: %s", error)
        return False


# Run the functions in the required order.
# Stop with exit code 1 if no books are available, the bucket cannot be created, or making it public fails.
def main():
    # 1) read the three command-line arguments
    list_file, index_path, bucket = parse_args()

    # 2) download books into the local "books" directory
    books = download_books(list_file, "books")

    if not books:
        logger.error("No books were downloaded.")
        sys.exit(1)

    # 3) check for or create the bucket
    if not create_bucket(bucket):
        sys.exit(1)

    # 4) make the bucket publicly readable
    if not make_public(bucket):
        sys.exit(1)

    # 5) upload the books
    uploaded = upload_files(bucket, books)

    # 6) upload the index page
    index_uploaded = upload_index(bucket, index_path)

    # 7) report whether the uploads succeeded and print the public URL
    if uploaded == len(books) and index_uploaded:
        logger.info(
            "Success! Visit https://%s.s3.amazonaws.com/index.html",
            bucket,
        )
    else:
        logger.error("Some files failed to upload.")
        sys.exit(1)


# run main() when this script is executed directly
if __name__ == "__main__":
    main()
