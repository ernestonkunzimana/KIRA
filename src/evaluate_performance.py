import json
import time
import os

def calculate_senior_metrics(log_file_path="src/detection_metrics.json"):
    """Calculates precision, recall, and F1-score to validate AI model accuracy."""
    if not os.path.exists(log_file_path):
        print(f"[EVAL WARNING] Performance log file '{log_file_path}' not found yet.")
        return

    with open(log_file_path, "r") as f:
        lines = f.readlines()

    y_true = []  # 1 for normal, -1 for anomaly/attack
    y_pred = []

    for line in lines:
        try:
            data = json.loads(line.strip())
            y_true.append(data["actual_ground_truth"])
            y_pred.append(data["ai_prediction"])
        except Exception:
            continue

    if len(y_true) == 0:
        print("[EVAL ERROR] Performance logs are currently empty.")
        return

    # Convert to numpy arrays for matrix evaluations
    actuals =  [1 if x == 1 else 0 for x in y_true]
    predictions = [1 if x == 1 else 0 for x in y_pred]

    # Calculate Confusion Matrix variables manually to avoid bloating edge memory dependencies
    tp = sum(1 for a, p in zip(actuals, predictions) if a == 0 and p == 0) # True Positives (Attacks caught)
    fp = sum(1 for a, p in zip(actuals, predictions) if a == 1 and p == 0) # False Positives (False alarms)
    fn = sum(1 for a, p in zip(actuals, predictions) if a == 0 and p == 1) # False Negatives (Missed attacks)
    tn = sum(1 for a, p in zip(actuals, predictions) if a == 1 and p == 1) # True Negatives (Correctly passed normal)

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1_score = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
    fpr = fp / (fp + tn) if (fp + tn) > 0 else 0.0

    print("\n=======================================================")
    print("      EDGE AI PERFORMANCE EVALUATION REPORT            ")
    print("=======================================================")
    print(f" Total Evaluated Stream Packets : {len(y_true)}")
    print(f" True Positives (Attacks Blocked): {tp}")
    print(f" False Positives (False Alarms)  : {fp}")
    print(f" False Negatives (Missed Attacks): {fn}")
    print("-------------------------------------------------------")
    print(f" Structural Precision          : {precision * 100:.2f}%")
    print(f" Detection Recall (Sensitivity): {recall * 100:.2f}%")
    print(f" Harmonized F1-Score           : {f1_score * 100:.2f}%")
    print(f" False Positive Rate (FPR)     : {fpr * 100:.2f}%")
    print("=======================================================\n")

if __name__ == "__main__":
    print("[EVAL INITIALIZER] Evaluating local edge pipelines...")
    calculate_senior_metrics()
