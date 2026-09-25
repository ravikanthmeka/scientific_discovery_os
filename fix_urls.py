import os
import sys

def fix_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        data = f.read()
        
    original = data
    data = data.replace('\'/chat\'', '${import.meta.env.VITE_BACKEND_URL}/chat')
    data = data.replace('\'/ws/discovery\'', '${import.meta.env.VITE_BACKEND_URL.replace("http", "ws")}/ws/discovery')
    data = data.replace('"/api/branch"', '${import.meta.env.VITE_BACKEND_URL}/api/branch')
    data = data.replace('"/simulate"', '${import.meta.env.VITE_BACKEND_URL}/simulate')
    
    if data != original:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(data)
        print("Fixed", filepath)

for root, dirs, files in os.walk('frontend/src'):
    for file in files:
        if file.endswith('.jsx'):
            fix_file(os.path.join(root, file))
