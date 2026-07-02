<div align="center">

<img src="https://img.shields.io/badge/SEU-GPA%20Calculator-brightgreen?style=for-the-badge&logo=python&logoColor=white" />
<img src="https://img.shields.io/badge/Python-3.8+-blue?style=for-the-badge&logo=python&logoColor=white" />
<img src="https://img.shields.io/badge/License-MIT-yellow?style=for-the-badge" />

</div>

<br />

# GPA Calculator for SEUer

> **Transparent. Auditable. Yours.**
>
> 一个从教务系统 JSON 数据中自动计算 Official GPA 与 Core Major GPA 的工具。不联网、不爬虫、不上传——所有计算在本地完成，每一分都可追溯。

---

## 快速开始

```bash
# 1. 从浏览器手动获取成绩 JSON → 保存为 成绩.txt
# 2. 运行
python main.py
```

程序会输出：
- 参与计算的**全部课程明细**
- **Official GPA**（必修 + 限选，100分制）
- **Core Major GPA**（专业核心课子集，100分制 & 4.0制）

---

## 数据获取（3 步）

| 步骤 | 操作 |
|:---:|---|
| **①** | 登录教务系统 → 进入成绩查询页面 |
| **②** | `F12` 打开开发者工具 → 切换到 **Network** 面板 |
| **③** | 点击查询/翻页 → 找到 `xscjcx.do` → **Response** 标签 → 复制全部 JSON |

多页成绩直接依次粘贴到同一个 `成绩.txt` 即可，无需分隔符。程序自动拼接。

---

## 计算口径

### Official GPA（制度口径）

$$\text{GPA}_{\text{official}} = \frac{\sum (\text{成绩} \times \text{学分})}{\sum \text{学分}}$$

- 纳入：**必修** + **限选**
- 权重：**XF（学分）**
- 成绩：优先 `ZCJ`（总评），自动回退到分项加权估算

### Core Major GPA（专业核心口径）

Official GPA 课程集合的**子集**，按关键词匹配：

```
电路  信号  通信  电子  数字  模拟  电磁
概率  随机  线性代数  数学分析  复变
计组  计算机组织  操作系统  Linux  微机系统
无线  网络
```

关键词可配置，支持显式黑名单排除。

### 等级制映射

| 等级 | 优 | 良 | 中 | 及格 | 不及格 |
|:---:|:---:|:---:|:---:|:---:|:---:|
| 数值 | 95 | 85 | 75 | 65 | 55 |

### 4.0 GPA 转换

| 百分制 | >=93 | 90-92 | 87-89 | 83-86 | 80-82 | 77-79 | 73-76 | 70-72 | 67-69 | 63-66 | <63 |
|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| GPA | 4.0 | 3.7 | 3.3 | 3.0 | 2.7 | 2.3 | 2.0 | 1.7 | 1.3 | 1.0 | 0.0 |

---

## 鲁棒性设计

针对教务系统 JSON 格式的常见变化，程序内置多层回退：

```
ZCJ (数值) → ZCJ (等级文字) → DJCJMC → XSZCJMC
→ _DISPLAY 字段 (等级/数值) → 分项加权估算 → 跳过
```

| 场景 | 处理方式 |
|---|---|
| `ZCJ = "待评教"` | 跳过，自动从 `XSZCJMC` / `QMCJ_DISPLAY` / 分项加权中恢复 |
| 五级制课程（`DJCJLXDM=500`） | 从 `DJCJMC` 或 `QMCJ_DISPLAY` 解析等级文字 |
| API 返回空占位行 | `isinstance(r, dict)` 过滤 |
| `xscjcx` 键名为 `null` | `isinstance` 守卫，自动回退遍历 `datas` |
| 哨兵值 `-501` | `parse_float_safe` 过滤负数 |
| 分项权重缺失 | 回退检查 `_DISPLAY` 后缀字段 |

---

## 自定义

编辑 `main.py` 即可：

```python
# Core Major 关键词
CORE_KEYWORDS = [
    "电路", "信号", "通信", ...
]

# 显式排除的课程
EXCLUDE_COURSES = [
    "电子信息类专业学习概论"
]
```

---

## 文件说明

```
.
├── main.py                 # 主程序
├── 成绩.txt                 # 你的成绩数据 (不提交)
├── 成绩（示例格式）.txt      # JSON 格式示例
├── 免责声明.txt              # 完整免责声明
├── README.md
└── .gitignore
```

> Windows 用户可直接下载 [Releases](https://github.com/EasonWheng/GPA-Calculator-For-SEUer/releases) 中的 exe 文件，无需安装 Python。

---

## 免责声明

本项目仅供学习与个人使用。程序**不会**自动访问任何网站、请求任何接口或上传任何数据。所有成绩数据必须由用户通过合法途径自行获取。详见 `免责声明.txt`。

---

<div align="center">

**MIT License** · Made with care for SEUer

</div>
