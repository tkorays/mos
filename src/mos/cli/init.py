import click
from pathlib import Path
import json
from typing import Optional
from mos.core.config import get_config
from mos.core.logging import get_logger
from mos.core.plugin import get_registry

logger = get_logger(__name__)


def _get_mos_dir():
    """获取 MOS 根目录"""
    return Path.home() / ".mos"


def _init_config_file(force=False):
    """初始化配置文件"""
    config_file = _get_mos_dir() / "config.json"

    if config_file.exists():
        if force:
            config_file.unlink()
            click.echo(f"  ⚠ 已删除旧配置文件: {config_file}")
        else:
            click.echo(f"  [OK] 配置文件已存在: {config_file}")
            return False

    config = get_config()
    config_dict = config.model_dump()

    config_file.parent.mkdir(parents=True, exist_ok=True)
    with open(config_file, 'w', encoding='utf-8') as f:
        json.dump(config_dict, f, indent=2, ensure_ascii=False)

    click.echo(f"  [OK] 已创建配置文件: {config_file}")
    return True


def _init_log_dir():
    """初始化日志目录"""
    log_dir = _get_mos_dir() / "logs"

    if log_dir.exists():
        click.echo(f"  [OK] 日志目录已存在: {log_dir}")
        return False

    log_dir.mkdir(parents=True, exist_ok=True)
    click.echo(f"  [OK] 已创建日志目录: {log_dir}")
    return True


def _init_cache_dir():
    """初始化缓存目录"""
    cache_dir = _get_mos_dir() / "cache"

    if cache_dir.exists():
        click.echo(f"  [OK] 缓存目录已存在: {cache_dir}")
        return False

    cache_dir.mkdir(parents=True, exist_ok=True)
    click.echo(f"  [OK] 已创建缓存目录: {cache_dir}")
    return True


def _init_plugin_dir():
    """初始化插件目录。

    使用 ``Config.plugin.plugin_path`` 作为根目录；首次安装的
    external 插件（通过 ``mos plugin install``）会被 ``git clone``
    到该目录下。
    """
    config = get_config()
    plugin_dir = Path(config.plugin.get_expanded_path())

    if plugin_dir.exists():
        click.echo(f"  [OK] 插件目录已存在: {plugin_dir}")
        return False

    plugin_dir.mkdir(parents=True, exist_ok=True)
    click.echo(f"  [OK] 已创建插件目录: {plugin_dir}")
    return True


def _init_core(force=False):
    """初始化 MOS 核心框架。"""
    click.echo()
    click.echo("=" * 60)
    click.echo("MOS 核心框架初始化")
    click.echo("=" * 60)
    click.echo()

    mos_dir = _get_mos_dir()
    click.echo(f"MOS 根目录: {mos_dir}")
    click.echo()

    if not mos_dir.exists():
        click.echo("创建 MOS 根目录...")
        mos_dir.mkdir(parents=True, exist_ok=True)
        click.echo(f"  [OK] 已创建: {mos_dir}")
    else:
        click.echo(f"  [OK] MOS 根目录已存在: {mos_dir}")

    click.echo()
    click.echo("初始化配置文件...")
    _init_config_file(force)

    click.echo()
    click.echo("初始化日志目录...")
    _init_log_dir()

    click.echo()
    click.echo("初始化缓存目录...")
    _init_cache_dir()

    click.echo()
    click.echo("初始化插件目录...")
    _init_plugin_dir()


def _init_plugin(plugin_name: str, force: bool = False):
    """初始化单个插件。"""
    registry = get_registry()
    plugin = registry.get(plugin_name)

    if plugin is None:
        click.echo(f"  [ERROR] 插件 '{plugin_name}' 未加载或未安装")
        return False

    if plugin.init is None:
        click.echo(f"  [SKIP] 插件 '{plugin_name}' 没有初始化函数")
        return False

    click.echo()
    click.echo("=" * 60)
    click.echo(f"初始化插件: {plugin_name}")
    click.echo("=" * 60)
    click.echo()

    try:
        plugin.init(force)
        click.echo()
        click.echo(f"[OK] 插件 '{plugin_name}' 初始化完成")
        return True
    except Exception as e:
        logger.error(f"Plugin {plugin_name} init failed: {e}")
        click.echo(f"  [ERROR] 插件 '{plugin_name}' 初始化失败: {e}")
        return False


def _init_all_plugins(force: bool = False):
    """初始化所有已加载的插件。"""
    registry = get_registry()
    plugins = registry.all()

    if not plugins:
        click.echo("  [INFO] 没有已加载的插件")
        return

    click.echo()
    click.echo("=" * 60)
    click.echo("初始化所有插件")
    click.echo("=" * 60)
    click.echo()

    initialized_count = 0
    skipped_count = 0

    for plugin in plugins:
        if plugin.init is None:
            click.echo(f"  [SKIP] 插件 '{plugin.name}' 没有初始化函数")
            skipped_count += 1
            continue

        click.echo(f"初始化插件: {plugin.name}")
        try:
            plugin.init(force)
            click.echo(f"  [OK] 插件 '{plugin.name}' 初始化完成")
            initialized_count += 1
        except Exception as e:
            logger.error(f"Plugin {plugin.name} init failed: {e}")
            click.echo(f"  [ERROR] 插件 '{plugin.name}' 初始化失败: {e}")

    click.echo()
    click.echo(f"初始化完成: {initialized_count} 个插件, {skipped_count} 个跳过")


@click.command()
@click.option('--force', '-f', is_flag=True, help='强制重新初始化（覆盖现有配置）')
@click.option('--plugin', '-p', 'plugin_name', help='初始化指定插件')
@click.option('--all', 'init_all', is_flag=True, help='初始化所有已加载的插件')
def init(force: bool, plugin_name: Optional[str], init_all: bool):
    """初始化 MOS 配置和环境

    首次使用或重新配置时运行此命令。
    将创建必要的配置文件和目录结构。

    使用方式：
        mos init              # 初始化核心框架
        mos init -p quant     # 初始化 quant 插件
        mos init --all        # 初始化所有插件
        mos init -f           # 强制重新初始化
    """
    # 如果指定了插件，只初始化插件
    if plugin_name:
        _init_plugin(plugin_name, force)
        return

    # 如果指定了 --all，初始化所有插件
    if init_all:
        _init_core(force)
        _init_all_plugins(force)
        return

    # 默认只初始化核心框架
    _init_core(force)

    click.echo()
    click.echo("=" * 60)
    click.echo("[OK] 初始化完成！")
    click.echo("=" * 60)
    click.echo()
    click.echo("接下来你可以：")
    click.echo("  1. 使用 'mos config list' 查看配置")
    click.echo("  2. 使用 'mos config set <key> <value>' 修改配置")
    click.echo("  3. 使用 'mos init -p <plugin>' 初始化插件")
    click.echo()
    click.echo("更多信息请参考项目文档")
    click.echo()
