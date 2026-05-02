import os
import torch
import torch.nn as nn
from torchvision import models, transforms
from torch.utils.data import Dataset
from PIL import Image
import cv2

class Alaska2Dataset(Dataset):
    def __init__(self, root_dir, transform=None):
        self.root_dir = root_dir
        self.transform = transform
        self.samples = []
        
        cover_dir = os.path.join(root_dir, 'Cover')
        if os.path.exists(cover_dir):
            for f in os.listdir(cover_dir):
                self.samples.append((os.path.join(cover_dir, f), 0))
        
        stego_dirs = {'JMiPOD': 1, 'JUNIWARD': 2, 'UERD': 3}
        for s_dir, label in stego_dirs.items():
            p = os.path.join(root_dir, s_dir)
            if os.path.exists(p):
                for f in os.listdir(p):
                    self.samples.append((os.path.join(p, f), label))

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx):
        path, label = self.samples[idx]
        image = Image.open(path).convert('RGB')
        if self.transform:
            image = self.transform(image)
        return image, label

def get_model():
    # Use ResNet18 for fast training and good baseline
    weights = models.ResNet18_Weights.DEFAULT
    model = models.resnet18(weights=weights)
    num_ftrs = model.fc.in_features
    # Multi-class classification: 0=Cover, 1=JMiPOD, 2=JUNIWARD, 3=UERD
    model.fc = nn.Linear(num_ftrs, 4)
    return model

class AI_Detector:
    def __init__(self, model_path='steg_model.pth'):
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        self.model = get_model().to(self.device)
        self.is_loaded = False
        
        if os.path.exists(model_path):
            try:
                self.model.load_state_dict(torch.load(model_path, map_location=self.device, weights_only=True))
                self.model.eval()
                self.is_loaded = True
            except Exception as e:
                print(f"Failed to load AI model: {e}")
        
        self.transform = transforms.Compose([
            transforms.Resize(256),
            transforms.CenterCrop(256),
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
        ])

    def predict(self, image_np):
        """Returns dict with Steganography presence, Method, and Confidence."""
        if not self.is_loaded:
            return None
            
        try:
            if len(image_np.shape) == 2:
                image_rgb = cv2.cvtColor(image_np, cv2.COLOR_GRAY2RGB)
            elif image_np.shape[2] == 4:
                image_rgb = cv2.cvtColor(image_np, cv2.COLOR_BGRA2RGB)
            else:
                image_rgb = cv2.cvtColor(image_np, cv2.COLOR_BGR2RGB)
                
            pil_img = Image.fromarray(image_rgb)
            tensor = self.transform(pil_img).unsqueeze(0).to(self.device)
            
            with torch.no_grad():
                outputs = self.model(tensor)
                probabilities = torch.nn.functional.softmax(outputs, dim=1)[0]
                
                # Extract predicted class
                pred_class = torch.argmax(probabilities).item()
                confidence = probabilities[pred_class].item()
                
                methods = {0: "None (Cover)", 1: "JMiPOD", 2: "JUNIWARD", 3: "UERD"}
                
                is_stego = (pred_class != 0)
                method = methods.get(pred_class, "Unknown")
                prob_stego = 1.0 - probabilities[0].item()
                
            return {
                "is_stego": is_stego,
                "method": method,
                "confidence": confidence,
                "prob_stego": prob_stego
            }
        except Exception as e:
            print(f"AI prediction error: {e}")
            return None
