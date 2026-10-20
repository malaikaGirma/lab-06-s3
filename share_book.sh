# start with a shebang and strict error handling (from lab instructions)
#!/bin/bash
set -euo pipefail

# check that all three required arguments were provided
if [ "$#" -ne 3 ]; then
    # print a usage message and exit 1 if any argument is missing
    echo "Usage: $0 <book_url> <bucket_name> <expiration_seconds>"
    exit 1
fi

# Store the three command-line arguments
URL="$1" #url of plain text
BUCKET="$2" #the name of the bucket
EXPIRATION="$3" #the expiration of the presigned URL in seconds

# download the book with curl into the books/ folder, keeping the file name from the URL
# 1) get the filename from the end of the URL
FILENAME="${URL##*/}"
# 2) create the books folder if it does not exist
mkdir -p books
# 3) download the book into the books folder
curl -kfL "$URL" -o "books/$FILENAME"


# create the bucket only if it does not already exist and is accessible
if aws s3 ls "s3://$BUCKET" > /dev/null 2>&1; then
    echo "Bucket already exists: $BUCKET"
else
    aws s3 mb "s3://$BUCKET"
fi

# upload the book as a private object with a text content type
aws s3 cp "books/$FILENAME" "s3://$BUCKET/$FILENAME" \
    --content-type "text/plain; charset=utf-8"

# generate a temporary URL that allows the book to be read
PRESIGNED_URL=$(aws s3 presign "s3://$BUCKET/$FILENAME" \
    --expires-in "$EXPIRATION")

# print the URL for the collaborator
echo "Presigned URL:"
echo "$PRESIGNED_URL"
