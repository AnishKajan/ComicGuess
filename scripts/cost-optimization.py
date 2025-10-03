#!/usr/bin/env python3
"""
Cost optimization script for ComicGuess Azure resources.
Analyzes usage patterns and provides recommendations for cost reduction.
"""

import os
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from azure.identity import DefaultAzureCredential
from azure.mgmt.consumption import ConsumptionManagementClient
from azure.mgmt.monitor import MonitorManagementClient
from azure.mgmt.cosmosdb import CosmosDBManagementClient
from azure.mgmt.storage import StorageManagementClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class CostOptimizer:
    def __init__(self, subscription_id: str, resource_group: str):
        self.subscription_id = subscription_id
        self.resource_group = resource_group
        self.credential = DefaultAzureCredential()
        
        # Initialize Azure clients
        self.consumption_client = ConsumptionManagementClient(
            self.credential, subscription_id
        )
        self.monitor_client = MonitorManagementClient(
            self.credential, subscription_id
        )
        self.cosmos_client = CosmosDBManagementClient(
            self.credential, subscription_id
        )
        self.storage_client = StorageManagementClient(
            self.credential, subscription_id
        )

    def analyze_cosmos_db_usage(self, account_name: str) -> Dict:
        """Analyze Cosmos DB RU/s usage and provide optimization recommendations."""
        try:
            # Get current throughput settings
            account = self.cosmos_client.database_accounts.get(
                self.resource_group, account_name
            )
            
            # Get usage metrics for the last 30 days
            end_time = datetime.utcnow()
            start_time = end_time - timedelta(days=30)
            
            metrics = self.monitor_client.metrics.list(
                resource_uri=account.id,
                timespan=f"{start_time.isoformat()}/{end_time.isoformat()}",
                interval='PT1H',
                metricnames='TotalRequestUnits,ProvisionedThroughput',
                aggregation='Average,Maximum'
            )
            
            recommendations = []
            current_cost_estimate = 0
            optimized_cost_estimate = 0
            
            # Analyze throughput utilization
            for metric in metrics.value:
                if metric.name.value == 'TotalRequestUnits':
                    avg_ru_usage = sum(point.average for point in metric.timeseries[0].data if point.average) / len(metric.timeseries[0].data)
                    max_ru_usage = max(point.maximum for point in metric.timeseries[0].data if point.maximum)
                    
                    # Current provisioned throughput (assuming 4000 RU/s max autoscale)
                    current_max_ru = 4000
                    current_cost_estimate = current_max_ru * 0.008 * 24 * 30  # $0.008 per RU/s per hour
                    
                    # Recommend optimal throughput based on usage patterns
                    recommended_max_ru = max(400, int(max_ru_usage * 1.2))  # 20% buffer
                    optimized_cost_estimate = recommended_max_ru * 0.008 * 24 * 30
                    
                    if recommended_max_ru < current_max_ru:
                        savings = current_cost_estimate - optimized_cost_estimate
                        recommendations.append({
                            'type': 'cosmos_throughput',
                            'current_max_ru': current_max_ru,
                            'recommended_max_ru': recommended_max_ru,
                            'avg_usage': avg_ru_usage,
                            'max_usage': max_ru_usage,
                            'monthly_savings': round(savings, 2),
                            'utilization_percent': round((avg_ru_usage / current_max_ru) * 100, 2)
                        })
            
            return {
                'account_name': account_name,
                'current_monthly_cost': round(current_cost_estimate, 2),
                'optimized_monthly_cost': round(optimized_cost_estimate, 2),
                'recommendations': recommendations
            }
            
        except Exception as e:
            logger.error(f"Error analyzing Cosmos DB usage: {e}")
            return {'error': str(e)}

    def analyze_storage_usage(self, storage_account_name: str) -> Dict:
        """Analyze blob storage usage and recommend tier optimizations."""
        try:
            # Get storage account metrics
            storage_account = self.storage_client.storage_accounts.get_properties(
                self.resource_group, storage_account_name
            )
            
            end_time = datetime.utcnow()
            start_time = end_time - timedelta(days=30)
            
            metrics = self.monitor_client.metrics.list(
                resource_uri=storage_account.id,
                timespan=f"{start_time.isoformat()}/{end_time.isoformat()}",
                interval='P1D',
                metricnames='UsedCapacity,Transactions,Egress',
                aggregation='Average,Total'
            )
            
            recommendations = []
            
            for metric in metrics.value:
                if metric.name.value == 'UsedCapacity':
                    avg_capacity_gb = sum(point.average for point in metric.timeseries[0].data if point.average) / (1024**3) / len(metric.timeseries[0].data)
                    
                    # Recommend storage tier based on access patterns
                    if avg_capacity_gb > 50:  # If storing more than 50GB
                        recommendations.append({
                            'type': 'storage_tier',
                            'current_tier': 'Hot',
                            'recommended_tier': 'Cool',
                            'capacity_gb': round(avg_capacity_gb, 2),
                            'estimated_monthly_savings': round(avg_capacity_gb * 0.01, 2)  # Approximate savings
                        })
            
            return {
                'storage_account': storage_account_name,
                'recommendations': recommendations
            }
            
        except Exception as e:
            logger.error(f"Error analyzing storage usage: {e}")
            return {'error': str(e)}

    def get_cost_alerts_status(self) -> Dict:
        """Check current budget and alert configurations."""
        try:
            # Get budgets for the resource group
            budgets = list(self.consumption_client.budgets.list(
                scope=f"/subscriptions/{self.subscription_id}/resourceGroups/{self.resource_group}"
            ))
            
            budget_status = []
            for budget in budgets:
                current_spend = budget.current_spend.amount if budget.current_spend else 0
                budget_amount = budget.amount
                utilization = (current_spend / budget_amount) * 100 if budget_amount > 0 else 0
                
                budget_status.append({
                    'name': budget.name,
                    'budget_amount': budget_amount,
                    'current_spend': current_spend,
                    'utilization_percent': round(utilization, 2),
                    'status': 'warning' if utilization > 75 else 'ok'
                })
            
            return {
                'budgets': budget_status,
                'total_budgets': len(budgets)
            }
            
        except Exception as e:
            logger.error(f"Error getting budget status: {e}")
            return {'error': str(e)}

    def generate_optimization_report(self, cosmos_account: str, storage_account: str) -> Dict:
        """Generate comprehensive cost optimization report."""
        report = {
            'generated_at': datetime.utcnow().isoformat(),
            'subscription_id': self.subscription_id,
            'resource_group': self.resource_group,
            'cosmos_analysis': self.analyze_cosmos_db_usage(cosmos_account),
            'storage_analysis': self.analyze_storage_usage(storage_account),
            'budget_status': self.get_cost_alerts_status()
        }
        
        # Calculate total potential savings
        total_savings = 0
        if 'recommendations' in report['cosmos_analysis']:
            for rec in report['cosmos_analysis']['recommendations']:
                if 'monthly_savings' in rec:
                    total_savings += rec['monthly_savings']
        
        if 'recommendations' in report['storage_analysis']:
            for rec in report['storage_analysis']['recommendations']:
                if 'estimated_monthly_savings' in rec:
                    total_savings += rec['estimated_monthly_savings']
        
        report['summary'] = {
            'total_monthly_savings_potential': round(total_savings, 2),
            'optimization_opportunities': len(report['cosmos_analysis'].get('recommendations', [])) + 
                                        len(report['storage_analysis'].get('recommendations', []))
        }
        
        return report

def main():
    """Main function to run cost optimization analysis."""
    subscription_id = os.getenv('AZURE_SUBSCRIPTION_ID')
    resource_group = os.getenv('AZURE_RESOURCE_GROUP', 'comicguess-rg')
    cosmos_account = os.getenv('COSMOS_ACCOUNT_NAME', 'comicguess-cosmos')
    storage_account = os.getenv('STORAGE_ACCOUNT_NAME', 'comicguessstorage')
    
    if not subscription_id:
        logger.error("AZURE_SUBSCRIPTION_ID environment variable is required")
        return
    
    optimizer = CostOptimizer(subscription_id, resource_group)
    report = optimizer.generate_optimization_report(cosmos_account, storage_account)
    
    # Save report to file
    report_file = f"cost-optimization-report-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
    with open(report_file, 'w') as f:
        json.dump(report, f, indent=2)
    
    logger.info(f"Cost optimization report saved to {report_file}")
    
    # Print summary
    print("\n=== COST OPTIMIZATION SUMMARY ===")
    print(f"Total monthly savings potential: ${report['summary']['total_monthly_savings_potential']}")
    print(f"Optimization opportunities: {report['summary']['optimization_opportunities']}")
    
    if report['cosmos_analysis'].get('recommendations'):
        print("\nCosmos DB Recommendations:")
        for rec in report['cosmos_analysis']['recommendations']:
            print(f"  - Reduce max RU/s from {rec['current_max_ru']} to {rec['recommended_max_ru']}")
            print(f"    Current utilization: {rec['utilization_percent']}%")
            print(f"    Monthly savings: ${rec['monthly_savings']}")
    
    if report['storage_analysis'].get('recommendations'):
        print("\nStorage Recommendations:")
        for rec in report['storage_analysis']['recommendations']:
            print(f"  - Change tier from {rec['current_tier']} to {rec['recommended_tier']}")
            print(f"    Monthly savings: ${rec['estimated_monthly_savings']}")

if __name__ == "__main__":
    main()