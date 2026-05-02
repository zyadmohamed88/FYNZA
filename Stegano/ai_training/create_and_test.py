import torch
import torch.nn as nn
from torchvision import models, transforms
from PIL import Image
import numpy as np
import os

# ===== Step 1: Create a realistic-looking synthetic photo =====
print("Creating a synthetic natural-looking image...")

# Simulate a natural photo: sky gradient + landscape colors + noise
width, height = 512, 512
img_array = np.zeros((height, width, 3), dtype=np.uint8)

# Sky gradient (top: light blue -> bottom: warm)
for y in range(height // 2):
    ratio = y / (height // 2)
    r = int(135 + ratio * 50)
    g = int(180 + ratio * 30)
    b = int(220 - ratio * 60)
    img_array[y, :] = [r, g, b]

# Ground / landscape (bottom half: greens and browns)
for y in range(height // 2, height):
    ratio = (y - height // 2) / (height // 2)
    r = int(80 - ratio * 30)
    g = int(120 - ratio * 40)
    b = int(60 - ratio * 20)
    img_array[y, :] = [r, g, b]

# Add realistic noise (like camera sensor noise)
noise = np.random.normal(0, 12, img_array.shape).astype(np.int16)
img_array = np.clip(img_array.astype(np.int16) + noise, 0, 255).astype(np.uint8)

# Add some texture variation across columns
for x in range(width):
    variation = np.random.randint(-5, 5, 3)
    img_array[:, x] = np.clip(img_array[:, x].astype(np.int16) + variation, 0, 255).astype(np.uint8)

# Save the image
img_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "synthetic_test.jpg")
img = Image.fromarray(img_array, 'RGB')
img.save(img_path, quality=95)
print(f"Image created and saved: {img_path}")

# ===== Step 2: Run the model on it =====
print("\nRunning the model...")

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

def get_model():
    model = models.resnet18(weights=None)
    num_ftrs = model.fc.in_features
    model.fc = nn.Linear(num_ftrs, 4)
    return model

transform = transforms.Compose([
    transforms.Resize(256),
    transforms.CenterCrop(256),
    transforms.ToTensor(),
    transforms.Normalize(
        mean=[0.485, 0.456, 0.406],
        std=[0.229, 0.224, 0.225]
    )
])

class_names = ["Cover", "JMiPOD", "JUNIWARD", "UERD"]

model = get_model().to(device)
weights_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "resnet18_stego.pth")
model.load_state_dict(torch.load(weights_path, map_location=device, weights_only=True))
model.eval()

img = Image.open(img_path).convert("RGB")
img_tensor = transform(img).unsqueeze(0).to(device)

with torch.no_grad():
    output = model(img_tensor)
    probabilities = torch.softmax(output, dim=1)
    all_probs = probabilities[0].tolist()
    confidence, pred = torch.max(probabilities, 1)
    index = pred.item()

method = class_names[index]
is_stego = index != 0
conf = confidence.item() * 100

print("\n" + "="*40)
print("PREDICTION RESULT")
print("="*40)
print(f"Result: {'[STEGO]' if is_stego else '[CLEAN]'}")
print(f"Classification: {method}")
print(f"Confidence: {conf:.2f}%")
print("\nAll class probabilities:")
for name, prob in zip(class_names, all_probs):
    bar = "#" * int(prob * 30)
    print(f"  {name:10s}: {prob*100:5.1f}% {bar}")
print("="*40)
