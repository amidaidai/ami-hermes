# Hermes config set YAML 数组写入陷阱

## 问题

`hermes config set platform_toolsets.telegram "['a', 'b', 'c']"` 不会写入 YAML 数组，而是写入**字符串字面量**：

```yaml
# 期望结果（数组）：
telegram:
  - browser
  - x_search

# 实际结果（字符串）：
telegram: '[''browser'', ''x_search'']'
```

这会导致 Hermes 读取配置时把数组当成字符串，工具集会无法正确加载。

## 根因

`hermes config set` 对嵌套 YAML 结构（特别是数组类型）的处理是**简单字符串替换**，不会解析输入值并写出正确的 YAML 结构。所有值都被当作标量写入。

## 修复方法

### 方法1：Python + PyYAML（推荐）

```bash
cd /c/Users/<user>/AppData/Local/hermes
python -c "
import yaml
with open('config.yaml', 'r', encoding='utf-8') as f:
    data = yaml.safe_load(f)

# 修改目标字段
data['platform_toolsets']['telegram'] = [
    'browser', 'clarify', 'code_execution', 'x_search'
    # ... 其他工具
]

with open('config.yaml', 'w', encoding='utf-8') as f:
    yaml.dump(data, f, default_flow_style=False, allow_unicode=True)
print('OK')
"
```

**注意**：`yaml.dump()` 会重新序列化整个文件，可能改变：
- 键的顺序（Python 3.7+ 保留 dict 插入顺序）
- 缩进风格（列表从 4 格变成 2 格，但 YAML 语法仍有效）
- 注释会被丢弃（PyYAML 不保留注释）

### 方法2：直接编辑文件（保留注释和格式）

```bash
hermes config edit
# 这会打开 $EDITOR（通常是 vim/nano），手动添加行
```

但 agent 不能直接调用交互式编辑器。

### 方法3：patch + terminal + python

```bash
# 用 python 直接做文本替换
python -c "
path = 'C:/Users/<user>/AppData/Local/hermes/config.yaml'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

old = '''  telegram: '[''browser'', ...]''
new = '''  telegram:
    - browser
    - x_search'''

content = content.replace(old, new)
with open(path, 'w', encoding='utf-8') as f:
    f.write(content)
print('Patched')
"
```

## 预防

- 修改 `platform_toolsets` 等含数组的嵌套结构时，**不要用** `hermes config set`
- 优先用 `hermes config edit`（交互式）或 Python + PyYAML 脚本
- 修改后用 `python -c "import yaml; d=yaml.safe_load(open('config.yaml')); ..."` 验证结构正确
- 验证数组是否为 list 类型而非字符串：`type(d['platform_toolsets']['telegram'])` 应为 `<class 'list'>`

## 补充：工具集变更需要重启会话

`config.yaml` 修改后，**当前运行的会话不会自动获得新工具**。必须：

| 渠道 | 操作 |
|------|------|
| Telegram / Discord 等网关 | 在对话中发 `/reset` |
| CLI | 退出后重新运行 `hermes` |
| Hermes Gateway 自身 | 不需要重启（gateway 会为新会话加载新配置） |

可以通过 `hermes tools list | grep <工具名>` 在 CLI 中确认新工具已启用。
