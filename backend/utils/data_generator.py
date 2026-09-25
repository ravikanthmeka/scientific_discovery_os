import argparse
import json
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import os

def generate_data(config, size):
    df = pd.DataFrame()
    
    # 1. Generate base columns
    for col in config.get("columns", []):
        name = col["name"]
        ctype = col.get("type", "normal")
        
        if ctype == "normal":
            df[name] = np.random.normal(col.get("mean", 0), col.get("std", 1), size)
        elif ctype == "uniform":
            df[name] = np.random.uniform(col.get("low", 0), col.get("high", 1), size)
        elif ctype == "categorical":
            vals = col.get("values", ["A", "B"])
            probs = col.get("probabilities", None)
            df[name] = np.random.choice(vals, size, p=probs)

    # 2. Apply rules/formulas (Simple eval over columns)
    for rule in config.get("rules", []):
        target = rule.get("target")
        formula = rule.get("formula")
        if target and formula:
            try:
                df[target] = df.eval(formula)
            except Exception as e:
                print(f"Warning: Failed to evaluate formula '{formula}' for target '{target}': {e}")
                df[target] = 0

    return df

def generate_plot(df, plot_config, output_dir):
    if not plot_config:
        return
        
    x = plot_config.get("x")
    y = plot_config.get("y")
    ptype = plot_config.get("type", "scatter")
    title = plot_config.get("title", f"{y} vs {x}")
    
    if x not in df.columns or y not in df.columns:
        print("Warning: Plot columns not found in dataframe.")
        return

    plt.figure(figsize=(8, 6))
    if ptype == "scatter":
        plt.scatter(df[x], df[y], alpha=0.5, s=10)
    elif ptype == "line":
        df_sorted = df.sort_values(by=x)
        plt.plot(df_sorted[x], df_sorted[y])
    elif ptype == "bar":
        agg = df.groupby(x)[y].mean()
        plt.bar(agg.index, agg.values)
        
    plt.title(title)
    plt.xlabel(x)
    plt.ylabel(y)
    plt.grid(True, linestyle='--', alpha=0.7)
    
    out_path = os.path.join(output_dir, "simulation_output.png")
    plt.savefig(out_path)
    print(f"Plot saved to {out_path}")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, help="Path to JSON config file")
    parser.add_argument("--size", type=int, default=100, help="Number of rows to generate")
    parser.add_argument("--outdir", default=".", help="Directory to save outputs")
    
    args = parser.parse_args()
    
    with open(args.config, 'r') as f:
        config = json.load(f)
        
    df = generate_data(config, args.size)
    
    csv_path = os.path.join(args.outdir, "simulation_preview.csv")
    df.to_csv(csv_path, index=False)
    
    plot_config = config.get("plot")
    if plot_config:
        generate_plot(df, plot_config, args.outdir)

if __name__ == "__main__":
    main()
