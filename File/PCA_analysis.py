import pandas as pd
import numpy as np
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA
import matplotlib.pyplot as plt #绘图的主要库

# 设置 Matplotlib 字体为支持中文的字体
plt.rcParams['font.sans-serif'] = ['SimHei']  # 设置字体为黑体
plt.rcParams['axes.unicode_minus'] = False  # 正确显示负号

# 1. 加载数据
file_path = r"C:\Users\姚乃高\Desktop\MY_labor's day\Disgusting reports\PCA\数据.csv"
data = pd.read_csv(file_path)

# 提取第2到45行的第4到20列数据（行索引1到44，列索引3到19）
X = data.iloc[1:46, 3:20].values  # 尝试提取45个样本，17个特征；。values转换为二维数据，赋值给X

# 检查实际提取的行数
n_samples = X.shape[0]
print(f"实际提取的样本数量: {n_samples}")

# 2. 数据标准化
scaler = StandardScaler()
X_std = scaler.fit_transform(X)#标准差标准化

# 3. 应用 PCA
pca = PCA(n_components=17)  # 保留所有17个主成分
X_pca = pca.fit_transform(X_std)

# 4. 查看方差贡献率
explained_variance_ratio = pca.explained_variance_ratio_
cumulative_variance = np.cumsum(explained_variance_ratio)
print("各主成分方差贡献率:\n", explained_variance_ratio)
print("累计方差贡献率:\n", cumulative_variance)

# 5. 载荷矩阵（主成分与原始变量的关系）
# 获取第4到20列的表头作为特征名
feature_names = data.columns[3:20].tolist()
loadings = pd.DataFrame(pca.components_.T, columns=[f'PC{i+1}' for i in range(17)], index=feature_names)
print("\n载荷矩阵:\n", loadings)

# 6. 可视化：方差贡献率柱状图
plt.figure(figsize=(8, 6))
#bar的参数列表：x轴、y轴、alpha（透明度）、label（图例）
plt.bar(range(1, 18), explained_variance_ratio, alpha=0.5, label='单个方差贡献率')
#plot的参数列表：x轴、y轴、颜色、标记、label（图例）
#标记：字符串，依次为颜色、线条样式、标记
plt.plot(range(1, 18), cumulative_variance, 'r-o', label='累计方差贡献率')
plt.xlabel('主成分')
plt.ylabel('方差贡献率')
plt.title('主成分的方差贡献率')
plt.legend()
plt.grid(True)
plt.show()

# 7. 可视化：主成分得分散点图（PC1 vs PC2）
plt.figure(figsize=(8, 6))
plt.scatter(X_pca[:, 0], X_pca[:, 1], c='blue', edgecolor='k')
plt.xlabel(f'主成分1(自然地质) ({explained_variance_ratio[0]*100:.2f}%)')
plt.ylabel(f'主成分2(农业活动)({explained_variance_ratio[1]*100:.2f}%)')
plt.title('主成分得分散点图')
# 为每个样本添加行号标注（根据实际样本数量动态调整）
for i in range(n_samples):
    plt.annotate(str(i+1), (X_pca[i, 0], X_pca[i, 1]))
# 添加 y=x 线
plt.plot([-4, 4], [-4, 4], 'r--')  # 从 (-4, -4) 到 (4, 4) 的虚线
plt.grid(True)
plt.show()

