import os
import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader
from torchvision import models, transforms
from PIL import Image
import numpy as np
import cv2
from tqdm import tqdm


class Alaska2Dataset(Dataset):
    def __init__(self, root_dir, transform=None):
        self.samples = []
        self.transform = transform

        class_map = {
            "Cover": 0,
            "JMiPOD": 1,
            "JUNIWARD": 2,
            "UERD": 3
        }

        for cls, label in class_map.items():
            folder = os.path.join(root_dir, cls)
            if os.path.exists(folder):
                for f in os.listdir(folder):
                    path = os.path.join(folder, f)
                    self.samples.append((path, label))

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx):
        path, label = self.samples[idx]

        try:
            image = Image.open(path).convert("RGB")
        except:
            # skip corrupted images
            return self.__getitem__((idx + 1) % len(self.samples))

        if self.transform:
            image = self.transform(image)

        return image, label

train_transform = transforms.Compose([
    transforms.Resize(280),
    transforms.RandomCrop(256),
    transforms.RandomHorizontalFlip(),
    transforms.RandomVerticalFlip(),
    transforms.RandomRotation(15),
    transforms.ToTensor(),
    transforms.Normalize(
        mean=[0.485, 0.456, 0.406],
        std=[0.229, 0.224, 0.225]
    )
])

val_transform = transforms.Compose([
    transforms.Resize(256),
    transforms.CenterCrop(256),
    transforms.ToTensor(),
    transforms.Normalize(
        mean=[0.485, 0.456, 0.406],
        std=[0.229, 0.224, 0.225]
    )
])

def get_model():
    model = models.resnet18(weights=models.ResNet18_Weights.DEFAULT)
    num_ftrs = model.fc.in_features
    model.fc = nn.Linear(num_ftrs, 4)
    return model

class TransformedDataset(Dataset):
    def __init__(self, subset, transform=None):
        self.subset = subset
        self.transform = transform
        
    def __getitem__(self, index):
        x, y = self.subset[index]
        # Subset returns the transformed image if the base dataset has transform
        # We want to override it or apply it here. 
        # Better: create two dataset objects.
        return x, y
        
    def __len__(self):
        return len(self.subset)


DATA_PATH = r"C:\steganography\steganography\Effecientnet\alaska2_sample" 

# Create two dataset instances to have different transforms
train_dataset_full = Alaska2Dataset(DATA_PATH, train_transform)
val_dataset_full = Alaska2Dataset(DATA_PATH, val_transform)

indices = torch.randperm(len(train_dataset_full)).tolist()
train_size = int(0.8 * len(train_dataset_full))

train_dataset = torch.utils.data.Subset(train_dataset_full, indices[:train_size])
val_dataset = torch.utils.data.Subset(val_dataset_full, indices[train_size:])

train_loader = DataLoader(train_dataset, batch_size=16, shuffle=True)
val_loader = DataLoader(val_dataset, batch_size=16, shuffle=False)

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
model = get_model().to(device)
criterion = nn.CrossEntropyLoss()
optimizer = torch.optim.Adam(model.parameters(), lr=2e-4) # Slightly higher initial LR
scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(optimizer, mode='max', factor=0.5, patience=2, verbose=True)

EPOCHS = 30 # Increased epochs for better learning
best_val_acc = 0

for epoch in range(EPOCHS):
    model.train()
    total_loss = 0
    loop = tqdm(train_loader, desc=f"Epoch {epoch+1}/{EPOCHS} [Train]")
    for imgs, labels in loop:
        imgs, labels = imgs.to(device), labels.to(device)
        outputs = model(imgs)
        loss = criterion(outputs, labels)
        optimizer.zero_grad()
        loss.backward()
        optimizer.step()
        total_loss += loss.item()
        loop.set_postfix(loss=loss.item())

    # Validation loop
    model.eval()
    correct = 0
    total = 0
    with torch.no_grad():
        for imgs, labels in val_loader:
            imgs, labels = imgs.to(device), labels.to(device)
            outputs = model(imgs)
            _, predicted = torch.max(outputs.data, 1)
            total += labels.size(0)
            correct += (predicted == labels).sum().item()
    
    val_acc = 100 * correct / total
    print(f"Epoch {epoch+1} - Loss: {total_loss/len(train_loader):.4f} - Val Acc: {val_acc:.2f}%")
    
    # Step scheduler
    scheduler.step(val_acc)
    
    # Save best model
    if val_acc > best_val_acc:
        best_val_acc = val_acc
        save_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "resnet18_stego.pth")
        torch.save(model.state_dict(), save_path)
        print(f"Saved new best model with accuracy: {val_acc:.2f}%")

# Save the model
save_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "resnet18_stego.pth")
torch.save(model.state_dict(), save_path)
print(f"Model saved to {save_path}")
