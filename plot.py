import matplotlib
matplotlib.use('Agg')
import os
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

for filename in os.listdir("static/plots"):
    os.remove(os.path.join("static/plots", filename))

df = pd.read_csv("generated_data.csv")

plt.figure(figsize=(8, 5))
plt.scatter(df["Salary"], df["HireDate"], marker="o", color="red")
plt.xlabel("Salary")
plt.ylabel("Hire Date")
plt.title("Salary vs Hire Date")
plt.savefig("static/plots/plot_1.png")

plt.figure(figsize=(8, 5))
sns.countplot(x="DepartmentID", data=df)
plt.xlabel("Department ID")
plt.ylabel("Number of Employees")
plt.title("Number of Employees by Department")
plt.savefig("static/plots/plot_2.png")

plt.figure(figsize=(8, 5))
sns.barplot(x="LastName", y="Salary", data=df)
plt.xlabel("Last Name")
plt.ylabel("Salary")
plt.title("Salary by Last Name")
plt.savefig("static/plots/plot_3.png")