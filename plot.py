import matplotlib.pyplot as plt
import pandas as pd

# Sample Data (will be replaced dynamically)
data = {'Category': ['A', 'B', 'C'], 'Values': [10, 20, 30]}
df = pd.DataFrame(data)

# Plot the data
plt.figure(figsize=(8,5))
plt.bar(df["Category"], df["Values"], color='skyblue')

# Save the figure
plt.savefig("static/plot.png")
print("Visualization saved as static/plot.png")
