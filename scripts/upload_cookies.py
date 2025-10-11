"""
Upload Instagram cookies to R2 storage
Run this after extracting cookies with yt-dlp
"""
import boto3
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv(Path(__file__).parent / '.env')

# Initialize R2 client
r2_client = boto3.client(
    's3',
    endpoint_url=f"https://{os.getenv('R2_ACCOUNT_ID')}.r2.cloudflarestorage.com",
    aws_access_key_id=os.getenv('R2_ACCESS_KEY_ID'),
    aws_secret_access_key=os.getenv('R2_SECRET_ACCESS_KEY'),
    region_name='auto'
)

# Upload cookies file
cookies_file = 'instagram_cookies_only.txt'
if not os.path.exists(cookies_file):
    print(f"❌ Error: {cookies_file} not found!")
    print(f"Please extract cookies first:")
    print(f'yt-dlp --cookies-from-browser chrome --cookies {cookies_file} "https://www.instagram.com/"')
    exit(1)

with open(cookies_file, 'rb') as f:
    r2_client.put_object(
        Bucket=os.getenv('R2_BUCKET_NAME'),
        Key='thumbnails/www.instagram.com_cookies.txt',
        Body=f,
        ContentType='text/plain'
    )

print("✅ Uploaded to R2: https://pub-69fc9d7b005d450285cb0cee6d8c0dd5.r2.dev/thumbnails/www.instagram.com_cookies.txt")
print("🚀 No service restart needed - changes take effect immediately!")
