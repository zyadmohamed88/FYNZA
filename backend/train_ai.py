import os
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, random_split
from torchvision import transforms
from ai_steganalysis import Alaska2Dataset, get_model

def train():
    print("Initializing training...")
    dataset_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'alaska2_sample')
    
    transform = transforms.Compose([
        transforms.Resize((256, 256)),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
    ])
    
    dataset = Alaska2Dataset(root_dir=dataset_path, transform=transform)
    if len(dataset) == 0:
        print("Error: Dataset not found or empty. Please check the alaska2_sample directory.")
        return
        
    print(f"Loaded {len(dataset)} samples.")
    
    train_size = int(0.8 * len(dataset))
    val_size = len(dataset) - train_size
    train_dataset, val_dataset = random_split(dataset, [train_size, val_size])
    
    train_loader = DataLoader(train_dataset, batch_size=32, shuffle=True, num_workers=0)
    val_loader = DataLoader(val_dataset, batch_size=32, shuffle=False, num_workers=0)
    
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"Using device: {device}")
    
    model = get_model().to(device)
    criterion = nn.CrossEntropyLoss()
    optimizer = optim.Adam(model.parameters(), lr=0.0001) # Small learning rate for fine-tuning
    
    num_epochs = 5
    best_acc = 0.0
    model_save_path = os.path.join(os.path.dirname(__file__), 'steg_model.pth')
    
    for epoch in range(num_epochs):
        model.train()
        running_loss = 0.0
        for i, (inputs, labels) in enumerate(train_loader):
            inputs, labels = inputs.to(device), labels.to(device)
            
            optimizer.zero_grad()
            outputs = model(inputs)
            loss = criterion(outputs, labels)
            loss.backward()
            optimizer.step()
            
            running_loss += loss.item()
            if i % 10 == 9:
                print(f"Epoch {epoch+1}/{num_epochs}, Batch {i+1}/{len(train_loader)}, Loss: {running_loss/10:.4f}")
                running_loss = 0.0
                
        # Validation
        model.eval()
        correct = 0
        total = 0
        with torch.no_grad():
            for inputs, labels in val_loader:
                inputs, labels = inputs.to(device), labels.to(device)
                outputs = model(inputs)
                _, predicted = torch.max(outputs.data, 1)
                total += labels.size(0)
                correct += (predicted == labels).sum().item()
                
        val_acc = 100 * correct / total
        print(f"Epoch {epoch+1} Validation Accuracy: {val_acc:.2f}%")
        
        # Save always to ensure we get a model, or if it improves
        if val_acc >= best_acc:
            best_acc = val_acc
            torch.save(model.state_dict(), model_save_path)
            print("Saved new best model!")

    print(f"Training complete. Best Validation Accuracy: {best_acc:.2f}%")
    print(f"Model saved to {model_save_path}")

if __name__ == '__main__':
    train()


