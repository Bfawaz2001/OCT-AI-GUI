import os
import pandas as pd
import torch
from torch.utils.data import DataLoader
from albumentations import Compose, Resize, Normalize
from albumentations.pytorch import ToTensorV2
from sklearn.metrics import classification_report, roc_auc_score, roc_curve, confusion_matrix, accuracy_score, precision_score, recall_score, f1_score
import matplotlib.pyplot as plt
import seaborn as sns
from tqdm import tqdm
from src.model.model import OCTModel
from src.data.dataset import OCTDataset
import logging
import numpy as np

# Configure logging
logging.basicConfig(level=logging.INFO)

def evaluate_classification_model(model_path, test_csv, test_image_dir, device="cpu"):
    logging.info(f"Using device: {device}")
    logging.info("Loading test data...")

    # Extract model name/version from the file path
    model_name_or_version = os.path.splitext(os.path.basename(model_path))[0]

    # Define output directory for evaluation graphs
    base_dir = os.path.dirname(__file__)  # Get the directory of the current script
    output_dir = os.path.join(base_dir, "evaluation graphs", "classification", model_name_or_version)
    os.makedirs(output_dir, exist_ok=True)

    # Load test data
    test_data = pd.read_csv(test_csv)
    label_columns = [col for col in test_data.columns if col != 'ID']
    num_classes = len(label_columns)

    logging.info(f"Inferred label columns for classification: {label_columns}")
    logging.info(f"Number of classes: {num_classes}")

    # Data transforms
    test_transform = Compose([
        Resize(224, 224),
        Normalize(mean=(0.485, 0.456, 0.406), std=(0.229, 0.224, 0.225)),
        ToTensorV2()
    ])

    # Dataset and DataLoader
    test_dataset = OCTDataset(
        test_data, label_columns, transform=test_transform, image_dir=test_image_dir
    )
    test_loader = DataLoader(test_dataset, batch_size=32, shuffle=False)

    # Load model
    model = OCTModel(num_classes=num_classes, dropout_rate=0.3).to(device)
    model.load_state_dict(torch.load(model_path, map_location=device))
    model.eval()

    # Metrics
    all_labels = []
    all_predictions = []
    all_probs = []

    logging.info("Evaluating model...")
    with torch.no_grad():
        for images, labels in tqdm(test_loader, desc="Evaluating"):
            images = images.to(device)
            labels = labels.to(device).float()

            outputs = torch.sigmoid(model(images))  # Use sigmoid for multi-label classification
            predictions = (outputs > 0.5).int()

            all_labels.append(labels.cpu().numpy())
            all_predictions.append(predictions.cpu().numpy())
            all_probs.append(outputs.cpu().numpy())

    # Flatten results
    all_labels = np.concatenate(all_labels, axis=0)
    all_predictions = np.concatenate(all_predictions, axis=0)
    all_probs = np.concatenate(all_probs, axis=0)

    # Compute overall metrics
    logging.info("Computing overall metrics...")
    accuracy = accuracy_score(all_labels.flatten(), all_predictions.flatten())
    precision = precision_score(all_labels.flatten(), all_predictions.flatten(), average='macro', zero_division=0)
    recall = recall_score(all_labels.flatten(), all_predictions.flatten(), average='macro', zero_division=0)
    f1 = f1_score(all_labels.flatten(), all_predictions.flatten(), average='macro', zero_division=0)

    logging.info(f"Overall Metrics:\nAccuracy: {accuracy:.4f}\nPrecision: {precision:.4f}\nRecall: {recall:.4f}\nF1 Score: {f1:.4f}")

    # Plot and save overall ROC curve
    plt.figure()
    for i, label in enumerate(label_columns):
        fpr, tpr, _ = roc_curve(all_labels[:, i], all_probs[:, i])
        auc = roc_auc_score(all_labels[:, i], all_probs[:, i])
        plt.plot(fpr, tpr, label=f"{label} (AUC = {auc:.4f})")
    plt.xlabel("False Positive Rate")
    plt.ylabel("True Positive Rate")
    plt.title("ROC Curves for All Diseases")
    plt.legend(loc="lower right")
    plt.grid()
    roc_path = os.path.join(output_dir, "roc_curves_all_diseases.png")
    plt.savefig(roc_path)
    logging.info(f"ROC Curves for All Diseases saved to {roc_path}")
    plt.close()

    # Compute per-disease metrics and confusion matrices
    for i, label in enumerate(label_columns):
        logging.info(f"Metrics for {label}:")
        report = classification_report(all_labels[:, i], all_predictions[:, i])
        logging.info(f"\n{report}")
        conf_matrix = confusion_matrix(all_labels[:, i], all_predictions[:, i])

        # Plot and save confusion matrix heatmap for each disease
        plt.figure(figsize=(8, 6))
        sns.heatmap(conf_matrix, annot=True, fmt='d', cmap="Blues", xticklabels=["Negative", "Positive"],
                    yticklabels=["Negative", "Positive"])
        plt.title(f"Confusion Matrix for {label}")
        plt.xlabel("Predicted Labels")
        plt.ylabel("True Labels")
        conf_matrix_path = os.path.join(output_dir, f"{label}_confusion_matrix.png")
        plt.savefig(conf_matrix_path)
        logging.info(f"Confusion Matrix for {label} saved to {conf_matrix_path}")
        plt.close()


if __name__ == "__main__":
    # Paths
    test_csv = "../../data/classification/RFMiD_Testing_Classification.csv"
    test_image_dir = "../../data/test/images"
    model_path = "../../model/disease_classification_model_v15.pth"

    # Device
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    # Evaluate the model
    evaluate_classification_model(model_path, test_csv, test_image_dir, device)
