#!/bin/bash

RELEASE_URL="https://github.com/Tsaiyue/EggPainTT_autoclip/releases/download/v1.0.0-test/test_video_autocliptt.zip"  
ZIP_FILE="test_video_autocliptt.zip"
EXTRACT_DIR="test_video_autocliptt" 
VIDEO1="london_test.mp4"   
VIDEO2="rio_test.mp4"

mkdir -p "$EXTRACT_DIR"

echo "=== Downloading test file ==="
if [ ! -f "$ZIP_FILE" ]; then
    if command -v curl &> /dev/null; then
        curl -L "$RELEASE_URL" -o "$ZIP_FILE"
    else
        wget "$RELEASE_URL" -O "$ZIP_FILE"
    fi

    if [ $? -ne 0 ]; then
        echo "❌ Error: Download failed! Please check the URL and network connection."
        exit 1
    else
        echo "✅ Download completed: $ZIP_FILE"
    fi
else
    echo "⚠️ ZIP file already exists, skipping download."
fi

# 2. Extract the ZIP file (modified to handle nested structure and ignore __MACOSX)
echo -e "\n=== Extracting ZIP file ==="
if [ -f "$ZIP_FILE" ]; then
    # Create a temporary directory for extraction
    TEMP_DIR=$(mktemp -d)
    
    # Extract to temp directory and ignore __MACOSX
    unzip -o "$ZIP_FILE" -d "$TEMP_DIR" -x "__MACOSX*"
    
    if [ $? -ne 0 ]; then
        echo "❌ Error: Extraction failed! Please check if the ZIP file is corrupted."
        rm -rf "$TEMP_DIR"
        exit 1
    else
        # Find the actual video directory (handle nested structure)
        VIDEO_DIR=$(find "$TEMP_DIR" -type d -name "test_video_autocliptt" 2>/dev/null | head -n 1)
        
        if [ -z "$VIDEO_DIR" ]; then
            echo "❌ Error: Could not find video directory in the ZIP file."
            ls -R "$TEMP_DIR"
            rm -rf "$TEMP_DIR"
            exit 1
        fi
        
        # Move contents to our target directory
        mv "$VIDEO_DIR"/* "$EXTRACT_DIR"/
        rm -rf "$TEMP_DIR"
        
        echo "✅ Extraction completed to directory: $EXTRACT_DIR/"
        echo "Extracted files:"
        ls -lh "$EXTRACT_DIR"
    fi
else
    echo "❌ Error: ZIP file does not exist."
    exit 1
fi

# 3. Check if video files exist (updated paths)
echo -e "\n=== Checking video files ==="
VIDEO1_PATH="$EXTRACT_DIR/$VIDEO1"
VIDEO2_PATH="$EXTRACT_DIR/$VIDEO2"

if [ ! -f "$VIDEO1_PATH" ] || [ ! -f "$VIDEO2_PATH" ]; then
    echo "❌ Error: Expected video files not found in the ZIP."
    echo "Actual file list:"
    ls "$EXTRACT_DIR"
    exit 1
else
    echo "✅ Video files found:"
    echo "- $VIDEO1_PATH"
    echo "- $VIDEO2_PATH"
fi

# 4. Process video 1
echo -e "\n=== Processing video 1: $VIDEO1 ==="
start_time=$(date +%s)
python ../auto_clip.py --input "$VIDEO1_PATH" 
if [ $? -eq 0 ]; then
    echo "✅ Video 1 processed successfully! Go for check the result in the output folder."
else
    echo "❌ Video 1 processing failed!"
fi
end_time=$(date +%s)
echo "Time taken: $((end_time - start_time)) seconds"

# 5. Process video 2
echo -e "\n=== Processing video 2: $VIDEO2 ==="
start_time=$(date +%s)
python ../auto_clip.py --input "$VIDEO2_PATH" 
if [ $? -eq 0 ]; then
    echo "✅ Video 2 processed successfully! Go for check the result in the output folder."
else
    echo "❌ Video 2 processing failed!"
fi
end_time=$(date +%s)
echo "Time taken: $((end_time - start_time)) seconds"

echo -e "\n=== All tests completed ==="