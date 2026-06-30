"""CLI 任务管理命令"""

import click
from mos.core.task import get_task_manager


@click.group()
def task():
    """后台任务管理命令"""
    pass


@task.command()
@click.option('--daemon', is_flag=True, help='以守护进程模式运行')
def start(daemon):
    """启动任务调度器

    默认前台运行，适合开发调试。
    使用 --daemon 参数以守护进程模式运行（生产环境）。
    """
    manager = get_task_manager()

    if daemon:
        manager.start_daemon()
        click.echo("守护进程已启动")
    else:
        manager.start_foreground()
        click.echo("前台运行已启动（按 Ctrl+C 停止）")


@task.command()
def stop():
    """停止守护进程"""
    manager = get_task_manager()
    manager.stop_daemon()
    click.echo("守护进程已停止")


@task.command()
def restart():
    """重启守护进程"""
    manager = get_task_manager()
    manager.restart_daemon()
    click.echo("守护进程已重启")


@task.command()
def status():
    """查看任务调度器状态"""
    manager = get_task_manager()
    status = manager.get_status()

    click.echo("任务调度器状态:")
    click.echo(f"  运行状态: {'运行中' if status['running'] else '已停止'}")
    if status['pid']:
        click.echo(f"  PID: {status['pid']}")
    click.echo(f"  任务数量: {status['task_count']}")


@task.command('list')
def list_tasks():
    """列出所有已注册的任务"""
    manager = get_task_manager()
    tasks = manager.list_tasks()

    if not tasks:
        click.echo("暂无已注册的任务")
        return

    click.echo("已注册任务:")
    for task in tasks:
        status_icon = "✓" if task.enabled else "✗"
        trigger_info = ""

        if task.trigger_type.value == "cron":
            trigger_info = f"cron: {task.trigger_config.get('cron', 'N/A')}"
        elif task.trigger_type.value == "interval":
            trigger_info = f"interval: {task.trigger_config}"
        elif task.trigger_type.value == "event":
            trigger_info = f"event: {task.trigger_config.get('event_type', 'N/A')}"

        click.echo(f"  [{status_icon}] {task.name} ({trigger_info})")
        if task.description:
            click.echo(f"      描述: {task.description}")


@task.command()
@click.argument('name')
def enable(name):
    """启用指定任务

    Args:
        name: 任务名称
    """
    manager = get_task_manager()
    manager.enable_task(name)
    click.echo(f"任务 '{name}' 已启用")


@task.command()
@click.argument('name')
def disable(name):
    """禁用指定任务

    Args:
        name: 任务名称
    """
    manager = get_task_manager()
    manager.disable_task(name)
    click.echo(f"任务 '{name}' 已禁用")


@task.command()
@click.argument('name')
def run(name):
    """立即执行指定任务（用于测试）

    Args:
        name: 任务名称
    """
    manager = get_task_manager()
    result = manager.run_task_now(name)

    if result['success']:
        click.echo(f"任务 '{name}' 执行成功")
    else:
        click.echo(f"任务 '{name}' 执行失败: {result['error']}")


@task.command()
@click.argument('name', required=False)
@click.option('-n', default=50, help='显示最后 N 条日志')
def logs(name, n):
    """查看任务执行日志

    Args:
        name: 任务名称（可选，不指定则显示所有日志）
        n: 显示最后 N 条日志
    """
    manager = get_task_manager()
    logs = manager.storage.load_execution_logs(task_name=name, limit=n)

    if not logs:
        click.echo("暂无执行日志")
        return

    click.echo(f"执行日志（最后 {len(logs)} 条):")
    for log in logs:
        status_icon = "✓" if log.status == "success" else "✗"
        click.echo(f"  [{status_icon}] {log.task_name} - {log.status}")
        click.echo(f"      开始时间: {log.started_at}")
        if log.finished_at:
            click.echo(f"      结束时间: {log.finished_at}")
        if log.duration:
            click.echo(f"      耗时: {log.duration:.2f}秒")
        if log.error:
            click.echo(f"      错误: {log.error}")
