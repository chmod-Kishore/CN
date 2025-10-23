#!/usr/bin/env python3
"""
Camera Diagnostic Tool
Run this to find and test your camera before using the main app
"""

import cv2
import sys

print("=" * 60)
print("🔍 CAMERA DIAGNOSTIC TOOL")
print("=" * 60)

# Check OpenCV version
print(f"\n✅ OpenCV Version: {cv2.__version__}")

# List video devices (Linux)
try:
    import os
    import glob
    
    video_devices = glob.glob('/dev/video*')
    if video_devices:
        print(f"\n📹 Found video devices: {video_devices}")
    else:
        print("\n⚠️  No /dev/video* devices found")
except:
    pass

# Test cameras 0-4
print("\n🔍 Testing camera indices...")
working_cameras = []

for idx in range(5):
    print(f"\nTesting camera {idx}...", end=" ")
    cap = cv2.VideoCapture(idx)
    
    if cap.isOpened():
        ret, frame = cap.read()
        if ret:
            # Apply selfie-style horizontal flip
            frame = cv2.flip(frame, 1)

            h, w, c = frame.shape
            print(f"✅ WORKS! Resolution: {w}x{h}")
            working_cameras.append(idx)
            
            # Try to show the frame
            try:
                cv2.imshow(f"Camera {idx} - Press any key to continue", frame)
                cv2.waitKey(2000)  # Show for 2 seconds
                cv2.destroyAllWindows()
            except:
                print("   (Could not display preview - running headless?)")
        else:
            print("❌ Opens but can't read frames")
    else:
        print("❌ Cannot open")
    
    cap.release()

# Summary
print("\n" + "=" * 60)
print("📊 SUMMARY")
print("=" * 60)

if working_cameras:
    print(f"✅ Found {len(working_cameras)} working camera(s): {working_cameras}")
    print(f"\n💡 Use camera index: {working_cameras[0]}")
    print("\nTo use in your app:")
    print(f"   client.start_video({working_cameras[0]})")
else:
    print("❌ No working cameras found!")
    print("\n🔧 TROUBLESHOOTING:")
    print("\n1. Check camera permissions:")
    print("   sudo usermod -a -G video $USER")
    print("   (then logout and login)")
    
    print("\n2. Check if camera is in use:")
    print("   lsof /dev/video0")
    
    print("\n3. For Raspberry Pi, enable camera:")
    print("   sudo modprobe bcm2835-v4l2")
    
    print("\n4. Install v4l-utils:")
    print("   sudo apt-get install v4l-utils")
    print("   v4l2-ctl --list-devices")
    
    print("\n5. Check camera connection:")
    print("   ls -l /dev/video*")
    
    print("\n6. Try with cheese or guvcview:")
    print("   cheese  # GUI camera viewer")
    print("   guvcview")

print("\n" + "=" * 60)
