"""
CLI tool for managing database backups and recovery operations
"""

import asyncio
import click
import json
from datetime import datetime
from typing import Optional, List

from app.database.backup import backup_manager
from app.config import get_settings


@click.group()
def backup_cli():
    """Database backup and recovery management commands"""
    pass


@backup_cli.command()
@click.option('--name', '-n', help='Custom backup name')
@click.option('--verify', '-v', is_flag=True, help='Verify backup after creation')
def create(name: Optional[str], verify: bool):
    """Create a new database backup"""
    async def _create_backup():
        try:
            click.echo("Creating database backup...")
            result = await backup_manager.create_backup(name)
            
            click.echo(f"✅ Backup created successfully: {result['backup_name']}")
            click.echo(f"   Timestamp: {result['timestamp']}")
            click.echo(f"   Database: {result['database']}")
            
            for container, info in result['containers'].items():
                status_icon = "✅" if info['status'] == 'completed' else "❌"
                click.echo(f"   {status_icon} {container}: {info['document_count']} documents")
            
            if verify:
                click.echo("\nVerifying backup integrity...")
                verification = await backup_manager.verify_backup_integrity(result['backup_name'])
                
                if verification['status'] == 'verified':
                    click.echo("✅ Backup verification passed")
                else:
                    click.echo("❌ Backup verification failed")
                    for container, info in verification['containers'].items():
                        if info['status'] != 'verified':
                            click.echo(f"   ❌ {container}: {info.get('error', 'Unknown error')}")
            
        except Exception as e:
            click.echo(f"❌ Backup failed: {e}")
            raise click.Abort()
    
    asyncio.run(_create_backup())


@backup_cli.command()
@click.option('--format', '-f', type=click.Choice(['table', 'json']), default='table', help='Output format')
def list(format: str):
    """List all available backups"""
    async def _list_backups():
        try:
            backups = await backup_manager.list_backups()
            
            if format == 'json':
                click.echo(json.dumps(backups, indent=2))
                return
            
            if not backups:
                click.echo("No backups found")
                return
            
            # Table format
            click.echo(f"{'Backup Name':<30} {'Timestamp':<20} {'Status':<10} {'Containers':<20} {'Size':<10}")
            click.echo("-" * 100)
            
            for backup in backups:
                containers_str = ', '.join(backup['containers'])
                size_mb = backup['size_bytes'] / (1024 * 1024)
                
                status_icon = "✅" if backup['status'] == 'completed' else "❌"
                
                click.echo(
                    f"{backup['backup_name']:<30} "
                    f"{backup['timestamp'][:19]:<20} "
                    f"{status_icon} {backup['status']:<8} "
                    f"{containers_str:<20} "
                    f"{size_mb:.1f}MB"
                )
                
        except Exception as e:
            click.echo(f"❌ Failed to list backups: {e}")
            raise click.Abort()
    
    asyncio.run(_list_backups())


@backup_cli.command()
@click.argument('backup_name')
@click.option('--target-db', help='Target database name (defaults to current)')
@click.option('--containers', help='Comma-separated list of containers to restore')
@click.option('--dry-run', is_flag=True, help='Show what would be restored without actually doing it')
def restore(backup_name: str, target_db: Optional[str], containers: Optional[str], dry_run: bool):
    """Restore from a backup"""
    async def _restore_backup():
        try:
            containers_list = None
            if containers:
                containers_list = [c.strip() for c in containers.split(',')]
            
            if dry_run:
                click.echo(f"🔍 Dry run - would restore backup: {backup_name}")
                if target_db:
                    click.echo(f"   Target database: {target_db}")
                if containers_list:
                    click.echo(f"   Containers: {', '.join(containers_list)}")
                else:
                    click.echo("   Containers: all")
                return
            
            # Confirm restore operation
            click.echo(f"⚠️  This will restore backup '{backup_name}'")
            if target_db:
                click.echo(f"   Target database: {target_db}")
            if containers_list:
                click.echo(f"   Containers: {', '.join(containers_list)}")
            else:
                click.echo("   Containers: all")
            
            if not click.confirm("Are you sure you want to proceed?"):
                click.echo("Restore cancelled")
                return
            
            click.echo("Starting restore operation...")
            result = await backup_manager.restore_backup(
                backup_name, target_db, containers_list
            )
            
            click.echo(f"✅ Restore completed successfully")
            click.echo(f"   Backup: {result['backup_name']}")
            click.echo(f"   Target database: {result['target_database']}")
            click.echo(f"   Timestamp: {result['timestamp']}")
            
            for container, info in result['containers'].items():
                status_icon = "✅" if info['status'] == 'completed' else "❌"
                click.echo(f"   {status_icon} {container}: {info['restored_count']} documents restored")
            
        except Exception as e:
            click.echo(f"❌ Restore failed: {e}")
            raise click.Abort()
    
    asyncio.run(_restore_backup())


@backup_cli.command()
@click.argument('backup_name')
def verify(backup_name: str):
    """Verify backup integrity"""
    async def _verify_backup():
        try:
            click.echo(f"Verifying backup: {backup_name}")
            result = await backup_manager.verify_backup_integrity(backup_name)
            
            if result['status'] == 'verified':
                click.echo("✅ Backup verification passed")
            else:
                click.echo("❌ Backup verification failed")
            
            click.echo(f"   Backup: {result['backup_name']}")
            click.echo(f"   Timestamp: {result['timestamp']}")
            
            for container, info in result['containers'].items():
                if info['status'] == 'verified':
                    click.echo(f"   ✅ {container}: {info['actual_count']} documents verified")
                else:
                    click.echo(f"   ❌ {container}: {info.get('error', 'Unknown error')}")
                    if 'expected_count' in info and 'actual_count' in info:
                        click.echo(f"      Expected: {info['expected_count']}, Found: {info['actual_count']}")
            
        except Exception as e:
            click.echo(f"❌ Verification failed: {e}")
            raise click.Abort()
    
    asyncio.run(_verify_backup())


@backup_cli.command()
@click.option('--retention-days', '-r', default=30, help='Retention period in days')
@click.option('--dry-run', is_flag=True, help='Show what would be deleted without actually doing it')
def cleanup(retention_days: int, dry_run: bool):
    """Clean up old backups"""
    async def _cleanup_backups():
        try:
            if dry_run:
                click.echo(f"🔍 Dry run - would delete backups older than {retention_days} days")
                
                # List backups that would be deleted
                from datetime import datetime, timedelta
                cutoff_date = datetime.utcnow() - timedelta(days=retention_days)
                backups = await backup_manager.list_backups()
                
                to_delete = []
                for backup in backups:
                    backup_date = datetime.fromisoformat(backup["timestamp"].replace('Z', '+00:00'))
                    if backup_date < cutoff_date:
                        to_delete.append(backup["backup_name"])
                
                if to_delete:
                    click.echo(f"   Would delete {len(to_delete)} backups:")
                    for backup_name in to_delete:
                        click.echo(f"   - {backup_name}")
                else:
                    click.echo("   No backups to delete")
                return
            
            click.echo(f"Cleaning up backups older than {retention_days} days...")
            result = await backup_manager.cleanup_old_backups(retention_days)
            
            if result['status'] == 'completed':
                click.echo(f"✅ Cleanup completed")
                click.echo(f"   Deleted {result['deleted_count']} backups")
                
                if result['deleted_backups']:
                    click.echo("   Deleted backups:")
                    for backup_name in result['deleted_backups']:
                        click.echo(f"   - {backup_name}")
            else:
                click.echo(f"❌ Cleanup failed: {result.get('error', 'Unknown error')}")
            
        except Exception as e:
            click.echo(f"❌ Cleanup failed: {e}")
            raise click.Abort()
    
    asyncio.run(_cleanup_backups())


@backup_cli.command()
def status():
    """Show backup system status"""
    async def _backup_status():
        try:
            result = await backup_manager.get_backup_status()
            
            status_icon = {
                'healthy': '✅',
                'warning': '⚠️',
                'unhealthy': '❌'
            }.get(result['status'], '❓')
            
            click.echo(f"Backup System Status: {status_icon} {result['status'].upper()}")
            click.echo(f"Total backups: {result.get('total_backups', 0)}")
            click.echo(f"RPO (Recovery Point Objective): {result.get('rpo_hours', 0)} hours")
            click.echo(f"RTO (Recovery Time Objective): {result.get('rto_minutes', 0)} minutes")
            click.echo(f"RPO Compliant: {'✅' if result.get('rpo_compliant') else '❌'}")
            
            if result.get('recent_backup'):
                backup = result['recent_backup']
                click.echo(f"\nMost recent backup:")
                click.echo(f"  Name: {backup['backup_name']}")
                click.echo(f"  Timestamp: {backup['timestamp']}")
                click.echo(f"  Status: {backup['status']}")
                click.echo(f"  Containers: {', '.join(backup['containers'])}")
            
            if result.get('error'):
                click.echo(f"\nError: {result['error']}")
            
        except Exception as e:
            click.echo(f"❌ Failed to get backup status: {e}")
            raise click.Abort()
    
    asyncio.run(_backup_status())


@backup_cli.command()
@click.option('--schedule', help='Cron schedule for automated backups (e.g., "0 2 * * *" for daily at 2 AM)')
def schedule(schedule: Optional[str]):
    """Configure automated backup scheduling"""
    if schedule:
        click.echo(f"Backup schedule set to: {schedule}")
        click.echo("Note: This requires setting up a cron job or Azure Function timer trigger")
        click.echo("Example cron job:")
        click.echo(f"  {schedule} cd /path/to/app && python -m cli.backup_manager create --verify")
    else:
        click.echo("Current backup schedule: Not configured")
        click.echo("Use --schedule option to set a cron schedule")


if __name__ == '__main__':
    backup_cli()