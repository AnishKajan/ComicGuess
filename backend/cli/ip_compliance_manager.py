"""
CLI tool for managing IP compliance, attribution, and takedown requests.
"""

import asyncio
import json
import csv
from typing import List, Dict, Any, Optional
from datetime import datetime
import click

from app.services.ip_compliance_service import IPComplianceService
from app.models.attribution import (
    Attribution,
    RightsHolder,
    LicenseType,
    generate_standard_attribution,
    get_rights_holder_from_universe
)
from app.repositories.puzzle_repository import PuzzleRepository
from app.database.connection import get_database

@click.group()
def ip_compliance():
    """IP Compliance management commands"""
    pass

@ip_compliance.command()
@click.option('--universe', type=click.Choice(['marvel', 'dc', 'image', 'all']), default='all',
              help='Universe to generate attributions for')
@click.option('--dry-run', is_flag=True, help='Show what would be created without actually creating')
async def generate_attributions(universe: str, dry_run: bool):
    """Generate missing attribution records for characters"""
    
    click.echo(f"Generating attributions for universe: {universe}")
    
    try:
        service = IPComplianceService()
        puzzle_repo = PuzzleRepository()
        
        # Get puzzles based on universe filter
        if universe == 'all':
            puzzles = await puzzle_repo.get_all_puzzles()
        else:
            puzzles = await puzzle_repo.get_puzzles_by_universe(universe)
        
        click.echo(f"Found {len(puzzles)} puzzles to check")
        
        created_count = 0
        skipped_count = 0
        
        for puzzle in puzzles:
            # Check if attribution already exists
            existing = await service.attribution_repo.get_attribution_by_character(puzzle.character)
            
            if existing:
                skipped_count += 1
                if not dry_run:
                    click.echo(f"  Skipped {puzzle.character} (already exists)")
                continue
            
            if dry_run:
                click.echo(f"  Would create attribution for: {puzzle.character} ({puzzle.universe})")
                created_count += 1
            else:
                # Create attribution
                attribution = await service.ensure_character_attribution(puzzle.character, puzzle.universe)
                created_count += 1
                click.echo(f"  Created attribution for: {puzzle.character}")
        
        click.echo(f"\nSummary:")
        click.echo(f"  Created: {created_count}")
        click.echo(f"  Skipped: {skipped_count}")
        
        if dry_run:
            click.echo("  (Dry run - no changes made)")
            
    except Exception as e:
        click.echo(f"Error generating attributions: {e}", err=True)

@ip_compliance.command()
@click.option('--format', type=click.Choice(['json', 'csv']), default='json',
              help='Output format for the report')
@click.option('--output', type=click.Path(), help='Output file path')
async def compliance_report(format: str, output: Optional[str]):
    """Generate IP compliance report"""
    
    click.echo("Generating IP compliance report...")
    
    try:
        service = IPComplianceService()
        report = await service.generate_compliance_report()
        
        if format == 'json':
            report_data = report.model_dump()
            report_json = json.dumps(report_data, indent=2, default=str)
            
            if output:
                with open(output, 'w') as f:
                    f.write(report_json)
                click.echo(f"Report saved to: {output}")
            else:
                click.echo(report_json)
        
        elif format == 'csv':
            if not output:
                output = f"compliance_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            
            with open(output, 'w', newline='') as csvfile:
                writer = csv.writer(csvfile)
                
                # Write summary
                writer.writerow(['Metric', 'Value'])
                writer.writerow(['Total Characters', report.total_characters])
                writer.writerow(['Attributed Characters', report.attributed_characters])
                writer.writerow(['Missing Attribution', report.missing_attribution])
                writer.writerow([''])
                
                # Write rights holder breakdown
                writer.writerow(['Rights Holder', 'Count'])
                for holder, count in report.rights_holder_breakdown.items():
                    writer.writerow([holder, count])
                writer.writerow([''])
                
                # Write compliance issues
                writer.writerow(['Compliance Issues'])
                for issue in report.compliance_issues:
                    writer.writerow([issue])
            
            click.echo(f"CSV report saved to: {output}")
        
        # Display summary
        click.echo(f"\nCompliance Summary:")
        click.echo(f"  Total Characters: {report.total_characters}")
        click.echo(f"  Attributed: {report.attributed_characters}")
        click.echo(f"  Missing Attribution: {report.missing_attribution}")
        click.echo(f"  Compliance Issues: {len(report.compliance_issues)}")
        
    except Exception as e:
        click.echo(f"Error generating report: {e}", err=True)

@ip_compliance.command()
@click.option('--universe', type=click.Choice(['marvel', 'dc', 'image']), required=True,
              help='Universe to generate report for')
async def universe_report(universe: str):
    """Generate attribution report for specific universe"""
    
    click.echo(f"Generating attribution report for {universe.upper()}...")
    
    try:
        service = IPComplianceService()
        report = await service.generate_attribution_report_by_universe(universe)
        
        click.echo(f"\n{universe.upper()} Attribution Report:")
        click.echo(f"  Rights Holder: {report['rights_holder']}")
        click.echo(f"  Total Characters: {report['total_characters']}")
        click.echo(f"  Attributed Characters: {report['attributed_characters']}")
        click.echo(f"  Attribution Coverage: {report['attribution_coverage']:.1%}")
        
        if report['missing_attributions']:
            click.echo(f"\nMissing Attributions:")
            for character in report['missing_attributions']:
                click.echo(f"  - {character}")
        
    except Exception as e:
        click.echo(f"Error generating universe report: {e}", err=True)

@ip_compliance.command()
@click.argument('character_name')
@click.option('--creator', help='Creator names')
@click.option('--first-appearance', help='First comic appearance')
@click.option('--image-source', help='Image source URL or description')
@click.option('--notes', help='Compliance notes')
async def update_attribution(character_name: str, creator: Optional[str], 
                           first_appearance: Optional[str], image_source: Optional[str],
                           notes: Optional[str]):
    """Update attribution information for a character"""
    
    click.echo(f"Updating attribution for: {character_name}")
    
    try:
        service = IPComplianceService()
        
        attribution = await service.update_character_attribution(
            character_name=character_name,
            creator_names=creator,
            first_appearance=first_appearance,
            image_source=image_source,
            compliance_notes=notes
        )
        
        if attribution:
            click.echo("Attribution updated successfully:")
            click.echo(f"  Character: {attribution.character_name}")
            click.echo(f"  Rights Holder: {attribution.rights_holder.value}")
            if attribution.creator_names:
                click.echo(f"  Creators: {attribution.creator_names}")
            if attribution.first_appearance:
                click.echo(f"  First Appearance: {attribution.first_appearance}")
        else:
            click.echo(f"No attribution found for character: {character_name}")
            
    except Exception as e:
        click.echo(f"Error updating attribution: {e}", err=True)

@ip_compliance.command()
async def review_needed():
    """List characters that need legal review"""
    
    click.echo("Characters needing legal review:")
    
    try:
        service = IPComplianceService()
        attributions = await service.get_characters_needing_review()
        
        if not attributions:
            click.echo("  No characters need review")
            return
        
        for attribution in attributions:
            click.echo(f"  - {attribution.character_name} ({attribution.rights_holder.value})")
            if attribution.legal_review_date:
                click.echo(f"    Last reviewed: {attribution.legal_review_date.strftime('%Y-%m-%d')}")
            else:
                click.echo(f"    Never reviewed")
        
        click.echo(f"\nTotal characters needing review: {len(attributions)}")
        
    except Exception as e:
        click.echo(f"Error getting characters needing review: {e}", err=True)

@ip_compliance.command()
@click.argument('character_name')
async def mark_reviewed(character_name: str):
    """Mark legal review as completed for a character"""
    
    click.echo(f"Marking legal review complete for: {character_name}")
    
    try:
        service = IPComplianceService()
        success = await service.mark_legal_review_completed(character_name)
        
        if success:
            click.echo("Legal review marked as completed")
        else:
            click.echo(f"No attribution found for character: {character_name}")
            
    except Exception as e:
        click.echo(f"Error marking review complete: {e}", err=True)

@ip_compliance.command()
@click.argument('character_name')
async def validate_fair_use(character_name: str):
    """Validate fair use compliance for a character"""
    
    click.echo(f"Validating fair use compliance for: {character_name}")
    
    try:
        service = IPComplianceService()
        validation = await service.validate_fair_use_compliance(character_name)
        
        if validation['compliant']:
            click.echo("✓ Character is compliant with fair use requirements")
        else:
            click.echo("✗ Character has compliance issues:")
            for issue in validation['issues']:
                click.echo(f"  - {issue}")
            
            click.echo("\nRecommendations:")
            for rec in validation['recommendations']:
                click.echo(f"  - {rec}")
        
    except Exception as e:
        click.echo(f"Error validating fair use: {e}", err=True)

@ip_compliance.command()
async def pending_takedowns():
    """List pending takedown requests"""
    
    click.echo("Pending takedown requests:")
    
    try:
        service = IPComplianceService()
        requests = await service.get_pending_takedown_requests()
        
        if not requests:
            click.echo("  No pending takedown requests")
            return
        
        for request in requests:
            click.echo(f"\nRequest ID: {request.id}")
            click.echo(f"  Character: {request.character_name}")
            click.echo(f"  Rights Holder: {request.rights_holder}")
            click.echo(f"  Type: {request.request_type}")
            click.echo(f"  Contact: {request.contact_email}")
            click.echo(f"  Received: {request.received_at.strftime('%Y-%m-%d %H:%M:%S')}")
            click.echo(f"  Details: {request.request_details[:100]}...")
        
        click.echo(f"\nTotal pending requests: {len(requests)}")
        
    except Exception as e:
        click.echo(f"Error getting pending takedowns: {e}", err=True)

@ip_compliance.command()
@click.argument('request_id')
@click.option('--remove-content', is_flag=True, default=True,
              help='Remove character content (default: True)')
@click.confirmation_option(prompt='Are you sure you want to process this takedown request?')
async def process_takedown(request_id: str, remove_content: bool):
    """Process a takedown request"""
    
    click.echo(f"Processing takedown request: {request_id}")
    
    try:
        service = IPComplianceService()
        success = await service.process_takedown_request(request_id, remove_content)
        
        if success:
            if remove_content:
                click.echo("✓ Takedown request processed and content removed")
            else:
                click.echo("✓ Takedown request processed (content not removed)")
        else:
            click.echo(f"✗ Failed to process takedown request: {request_id}")
            
    except Exception as e:
        click.echo(f"Error processing takedown: {e}", err=True)

@ip_compliance.command()
@click.option('--output', type=click.Path(), required=True,
              help='Output file path for exported data')
async def export_data(output: str):
    """Export all attribution data for backup/audit"""
    
    click.echo("Exporting attribution data...")
    
    try:
        service = IPComplianceService()
        export_data = await service.export_attribution_data()
        
        with open(output, 'w') as f:
            json.dump(export_data, f, indent=2, default=str)
        
        click.echo(f"Attribution data exported to: {output}")
        click.echo(f"  Total attributions: {export_data['total_attributions']}")
        click.echo(f"  Total takedown requests: {export_data['total_takedown_requests']}")
        
    except Exception as e:
        click.echo(f"Error exporting data: {e}", err=True)

@ip_compliance.command()
@click.argument('input_file', type=click.Path(exists=True))
async def import_attributions(input_file: str):
    """Import attribution data from JSON file"""
    
    click.echo(f"Importing attributions from: {input_file}")
    
    try:
        with open(input_file, 'r') as f:
            data = json.load(f)
        
        if 'attributions' not in data:
            click.echo("Error: Input file must contain 'attributions' key", err=True)
            return
        
        service = IPComplianceService()
        imported_count = await service.import_attribution_data(data['attributions'])
        
        click.echo(f"Successfully imported {imported_count} attribution records")
        
    except Exception as e:
        click.echo(f"Error importing attributions: {e}", err=True)

def run_async_command(func):
    """Wrapper to run async commands"""
    def wrapper(*args, **kwargs):
        return asyncio.run(func(*args, **kwargs))
    return wrapper

# Apply async wrapper to all commands
for command in ip_compliance.commands.values():
    if asyncio.iscoroutinefunction(command.callback):
        command.callback = run_async_command(command.callback)

if __name__ == '__main__':
    ip_compliance()