"""
CLI tool for managing storage reliability and disaster recovery
"""

import asyncio
import click
import json
from datetime import datetime
from typing import Optional

from app.storage.reliability import storage_reliability


@click.group()
def storage_cli():
    """Storage reliability and disaster recovery management commands"""
    pass


@storage_cli.command()
def configure():
    """Configure storage lifecycle policies and reliability features"""
    async def _configure_storage():
        try:
            click.echo("Configuring storage lifecycle policies...")
            
            # Configure lifecycle policies
            lifecycle_result = await storage_reliability.configure_lifecycle_policies()
            if lifecycle_result["status"] == "configured":
                click.echo("✅ Lifecycle policies configured")
                click.echo(f"   Soft delete retention: {lifecycle_result['soft_delete_retention_days']} days")
                click.echo(f"   Version retention: {lifecycle_result['version_retention_days']} days")
                click.echo(f"   Archive after: {lifecycle_result['archive_after_days']} days")
            else:
                click.echo(f"❌ Failed to configure lifecycle policies: {lifecycle_result.get('error')}")
            
            # Enable soft delete
            click.echo("\nEnabling soft delete...")
            soft_delete_result = await storage_reliability.enable_soft_delete()
            if soft_delete_result["status"] == "enabled":
                click.echo("✅ Soft delete enabled")
                click.echo(f"   Retention: {soft_delete_result['retention_days']} days")
            else:
                click.echo(f"❌ Failed to enable soft delete: {soft_delete_result.get('error')}")
            
            # Enable versioning
            click.echo("\nEnabling blob versioning...")
            versioning_result = await storage_reliability.enable_versioning()
            if versioning_result["status"] == "enabled":
                click.echo("✅ Blob versioning enabled")
                click.echo(f"   Version retention: {versioning_result['version_retention_days']} days")
            else:
                click.echo(f"❌ Failed to enable versioning: {versioning_result.get('error')}")
            
        except Exception as e:
            click.echo(f"❌ Configuration failed: {e}")
            raise click.Abort()
    
    asyncio.run(_configure_storage())


@storage_cli.command()
@click.argument('blob_path')
def backup(blob_path: str):
    """Create a backup copy of a blob"""
    async def _backup_blob():
        try:
            click.echo(f"Creating backup of: {blob_path}")
            result = await storage_reliability.create_backup_copy(blob_path)
            
            if result["status"] == "completed":
                click.echo("✅ Backup created successfully")
                click.echo(f"   Source: {result['source_path']}")
                click.echo(f"   Backup: {result['backup_path']}")
                click.echo(f"   Container: {result['backup_container']}")
                click.echo(f"   Timestamp: {result['timestamp']}")
            else:
                click.echo(f"❌ Backup failed: {result.get('error')}")
                raise click.Abort()
            
        except Exception as e:
            click.echo(f"❌ Backup operation failed: {e}")
            raise click.Abort()
    
    asyncio.run(_backup_blob())


@storage_cli.command()
@click.argument('backup_path')
@click.option('--target', '-t', help='Target path for restoration (defaults to original path)')
def restore(backup_path: str, target: Optional[str]):
    """Restore a blob from backup"""
    async def _restore_blob():
        try:
            click.echo(f"Restoring from backup: {backup_path}")
            if target:
                click.echo(f"Target path: {target}")
            
            result = await storage_reliability.restore_from_backup(backup_path, target)
            
            if result["status"] == "completed":
                click.echo("✅ Restore completed successfully")
                click.echo(f"   Backup: {result['backup_path']}")
                click.echo(f"   Restored to: {result['restored_path']}")
                click.echo(f"   Timestamp: {result['timestamp']}")
            else:
                click.echo(f"❌ Restore failed: {result.get('error')}")
                raise click.Abort()
            
        except Exception as e:
            click.echo(f"❌ Restore operation failed: {e}")
            raise click.Abort()
    
    asyncio.run(_restore_blob())


@storage_cli.command()
@click.argument('blob_path')
@click.option('--format', '-f', type=click.Choice(['table', 'json']), default='table', help='Output format')
def versions(blob_path: str, format: str):
    """List all versions of a blob"""
    async def _list_versions():
        try:
            click.echo(f"Listing versions for: {blob_path}")
            versions_list = await storage_reliability.list_blob_versions(blob_path)
            
            if not versions_list:
                click.echo("No versions found")
                return
            
            if format == 'json':
                click.echo(json.dumps(versions_list, indent=2))
                return
            
            # Table format
            click.echo(f"\n{'Version ID':<20} {'Current':<8} {'Last Modified':<20} {'Size':<10} {'ETag':<15}")
            click.echo("-" * 80)
            
            for version in versions_list:
                current_marker = "✅" if version.get('is_current_version') else ""
                size_kb = (version.get('size', 0) / 1024) if version.get('size') else 0
                last_modified = version.get('last_modified', '')[:19] if version.get('last_modified') else ''
                etag = version.get('etag', '')[:12] if version.get('etag') else ''
                
                click.echo(
                    f"{version.get('version_id', 'N/A'):<20} "
                    f"{current_marker:<8} "
                    f"{last_modified:<20} "
                    f"{size_kb:.1f}KB{'':<5} "
                    f"{etag:<15}"
                )
            
        except Exception as e:
            click.echo(f"❌ Failed to list versions: {e}")
            raise click.Abort()
    
    asyncio.run(_list_versions())


@storage_cli.command()
@click.argument('blob_path')
@click.argument('version_id')
def restore_version(blob_path: str, version_id: str):
    """Restore a specific version of a blob"""
    async def _restore_version():
        try:
            click.echo(f"Restoring version {version_id} of: {blob_path}")
            
            if not click.confirm("This will overwrite the current version. Continue?"):
                click.echo("Operation cancelled")
                return
            
            result = await storage_reliability.restore_blob_version(blob_path, version_id)
            
            if result["status"] == "completed":
                click.echo("✅ Version restored successfully")
                click.echo(f"   Blob: {result['blob_path']}")
                click.echo(f"   Restored version: {result['restored_version']}")
                click.echo(f"   Timestamp: {result['timestamp']}")
            else:
                click.echo(f"❌ Version restore failed: {result.get('error')}")
                raise click.Abort()
            
        except Exception as e:
            click.echo(f"❌ Version restore operation failed: {e}")
            raise click.Abort()
    
    asyncio.run(_restore_version())


@storage_cli.command()
@click.option('--format', '-f', type=click.Choice(['table', 'json']), default='table', help='Output format')
def health():
    """Perform storage health check"""
    async def _health_check():
        try:
            click.echo("Performing storage health check...")
            result = await storage_reliability.perform_storage_health_check()
            
            if format == 'json':
                click.echo(json.dumps(result, indent=2))
                return
            
            # Table format
            status_icon = {
                'healthy': '✅',
                'warning': '⚠️',
                'unhealthy': '❌'
            }.get(result['overall_status'], '❓')
            
            click.echo(f"\nOverall Status: {status_icon} {result['overall_status'].upper()}")
            click.echo(f"Timestamp: {result['timestamp']}")
            
            # Container health
            click.echo(f"\nContainer Health:")
            for container_name, container_info in result.get('containers', {}).items():
                container_status = container_info.get('status', 'unknown')
                status_icon = {
                    'healthy': '✅',
                    'missing': '⚠️',
                    'unhealthy': '❌'
                }.get(container_status, '❓')
                
                click.echo(f"  {status_icon} {container_name}: {container_status}")
                
                if container_status == 'healthy':
                    blob_count = container_info.get('blob_count', 0)
                    total_size_mb = container_info.get('total_size_bytes', 0) / (1024 * 1024)
                    click.echo(f"    Blobs: {blob_count}, Size: {total_size_mb:.1f}MB")
                elif 'error' in container_info:
                    click.echo(f"    Error: {container_info['error']}")
            
            # Policy status
            click.echo(f"\nPolicy Configuration:")
            policies = result.get('policies', {})
            for policy_name, policy_status in policies.items():
                status_icon = "✅" if policy_status in ['configured', 'enabled'] else "❌"
                click.echo(f"  {status_icon} {policy_name}: {policy_status}")
            
            # Redundancy status
            click.echo(f"\nRedundancy Configuration:")
            redundancy = result.get('redundancy', {})
            for redundancy_name, redundancy_status in redundancy.items():
                if isinstance(redundancy_status, bool):
                    status_icon = "✅" if redundancy_status else "❌"
                    click.echo(f"  {status_icon} {redundancy_name}: {'enabled' if redundancy_status else 'disabled'}")
                else:
                    click.echo(f"  ℹ️  {redundancy_name}: {redundancy_status}")
            
        except Exception as e:
            click.echo(f"❌ Health check failed: {e}")
            raise click.Abort()
    
    asyncio.run(_health_check())


@storage_cli.command()
@click.option('--format', '-f', type=click.Choice(['table', 'json']), default='table', help='Output format')
def metrics():
    """Get storage usage and performance metrics"""
    async def _get_metrics():
        try:
            click.echo("Collecting storage metrics...")
            result = await storage_reliability.get_storage_metrics()
            
            if format == 'json':
                click.echo(json.dumps(result, indent=2))
                return
            
            if result.get('status') == 'failed':
                click.echo(f"❌ Failed to collect metrics: {result.get('error')}")
                return
            
            # Table format
            click.echo(f"\nStorage Metrics (as of {result['timestamp']})")
            click.echo("=" * 60)
            
            # Totals
            totals = result.get('totals', {})
            click.echo(f"Total Blobs: {totals.get('total_blobs', 0)}")
            click.echo(f"Total Size: {totals.get('total_size_mb', 0):.1f}MB")
            
            # Container breakdown
            click.echo(f"\nContainer Breakdown:")
            click.echo(f"{'Container':<25} {'Blobs':<8} {'Size (MB)':<12} {'Marvel':<8} {'DC':<8} {'Image':<8} {'Other':<8}")
            click.echo("-" * 80)
            
            for container_name, container_metrics in result.get('containers', {}).items():
                if container_metrics.get('status') == 'not_found':
                    click.echo(f"{container_name:<25} {'N/A':<8} {'N/A':<12} {'N/A':<8} {'N/A':<8} {'N/A':<8} {'N/A':<8}")
                    continue
                
                blob_count = container_metrics.get('blob_count', 0)
                size_mb = container_metrics.get('total_size_bytes', 0) / (1024 * 1024)
                
                universes = container_metrics.get('universes', {})
                marvel_count = universes.get('marvel', 0)
                DC_count = universes.get('DC', 0)
                image_count = universes.get('image', 0)
                other_count = universes.get('other', 0)
                
                click.echo(
                    f"{container_name:<25} "
                    f"{blob_count:<8} "
                    f"{size_mb:<12.1f} "
                    f"{marvel_count:<8} "
                    f"{DC_count:<8} "
                    f"{image_count:<8} "
                    f"{other_count:<8}"
                )
            
        except Exception as e:
            click.echo(f"❌ Failed to get metrics: {e}")
            raise click.Abort()
    
    asyncio.run(_get_metrics())


@storage_cli.command()
def drill():
    """Run disaster recovery drill"""
    async def _run_drill():
        try:
            click.echo("Starting disaster recovery drill...")
            click.echo("This will test backup and restore procedures with test data.")
            
            if not click.confirm("Continue with disaster recovery drill?"):
                click.echo("Drill cancelled")
                return
            
            result = await storage_reliability.run_disaster_recovery_drill()
            
            status_icon = {
                'passed': '✅',
                'failed': '❌',
                'in_progress': '⏳'
            }.get(result['status'], '❓')
            
            click.echo(f"\nDisaster Recovery Drill: {status_icon} {result['status'].upper()}")
            click.echo(f"Drill ID: {result['drill_id']}")
            click.echo(f"Timestamp: {result['timestamp']}")
            
            # Test results
            click.echo(f"\nTest Results:")
            for test_name, test_result in result.get('tests', {}).items():
                test_status = test_result.get('status', 'unknown')
                test_icon = "✅" if test_status == 'passed' else "❌"
                
                click.echo(f"  {test_icon} {test_name}: {test_status}")
                
                if test_status == 'failed' and 'error' in test_result:
                    click.echo(f"    Error: {test_result['error']}")
                elif 'details' in test_result:
                    details = test_result['details']
                    if isinstance(details, dict) and 'backup_path' in details:
                        click.echo(f"    Backup path: {details['backup_path']}")
            
            if result['status'] == 'failed' and 'error' in result:
                click.echo(f"\nOverall Error: {result['error']}")
            
            # Recommendations
            if result['status'] == 'passed':
                click.echo(f"\n✅ All disaster recovery tests passed!")
                click.echo("   Your storage system is ready for disaster recovery scenarios.")
            else:
                click.echo(f"\n⚠️  Some disaster recovery tests failed.")
                click.echo("   Please review the errors and fix any issues before relying on DR procedures.")
            
        except Exception as e:
            click.echo(f"❌ Disaster recovery drill failed: {e}")
            raise click.Abort()
    
    asyncio.run(_run_drill())


if __name__ == '__main__':
    storage_cli()