# Hermes Agent 工作区结构

这个仓库是棠溪的 Hermes 个性化配置工作区。

## 目录约定

- `hermes/`：Hermes 个性化配置、人格、记忆、定时任务和维护脚本。
- `hermes/scripts/`：可复用维护脚本。
- `hermes/scripts/repo-maintenance/`：GitHub 仓库重置、备份、远端维护相关脚本。
- `hermes/secrets/`：本机敏感凭据或临时 token，不备份到 GitHub。
- `projects/`：长期项目，不默认备份到该配置仓库。
- `sandbox/`：临时实验、测试和一次性工作。
- `outputs/`：报告、导出文件、生成物。

## 根目录原则

根目录只保留仓库级文件，例如 `.gitignore`、`README.md` 和顶层配置说明。具体项目、临时文件、导出产物和敏感文件都放入对应子目录。
