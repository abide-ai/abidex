#!/usr/bin/env python3
"""
End-to-End Fraud Detection Agent Pipeline Demo

This demonstrates a complete fraud detection system with multiple agents:
- Data Collection Agent: Fetches user and transaction data
- Risk Analysis Agent: Analyzes fraud risk and makes decisions
- Alert Management Agent: Handles notifications and alerts

All agents are fully instrumented with comprehensive telemetry using Abide AgentKit.
"""

import sys
import os
import time
import json
import random
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from enum import Enum

# Add the package to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from abidex import TelemetryClient, AgentRun, get_agent_logger, get_logger
from abidex.sinks import JSONLSink
from abidex.workflows.paths import resolve_workflow_log_path


# Data Models
@dataclass
class Transaction:
    transaction_id: str
    user_id: str
    amount: float
    merchant: str
    location: str
    timestamp: datetime
    payment_method: str
    
class RiskLevel(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

@dataclass
class UserProfile:
    user_id: str
    account_age_days: int
    avg_transaction_amount: float
    transaction_count: int
    risk_score: float
    location_history: List[str]
    flagged_previously: bool

@dataclass
class RiskAssessment:
    transaction_id: str
    risk_level: RiskLevel
    risk_score: float
    factors: List[str]
    decision: str  # "approve", "flag", "block"
    confidence: float


class DataCollectionAgent:
    """Agent responsible for collecting and enriching transaction data."""
    
    def __init__(self, client: TelemetryClient):
        self.client = client
        self.agent_name = "Data Collection Agent"
        self.agent_role = "data-processor"
        # Use get_agent_logger for agent-specific logging with role
        self.logger = get_agent_logger(self.agent_name, client=client, role=self.agent_role)
        
    def fetch_user_data(self, user_id: str, run_id: str) -> UserProfile:
        """Fetch comprehensive user profile data."""
        
        # Use agent logger with context
        logger = self.logger.with_context(run_id=run_id)
        
        # Agent thinking about what data to fetch
        logger.thinking(
            f"I need to fetch comprehensive user profile data for user {user_id}",
            context={"user_id": user_id, "data_sources": ["user_db", "transaction_history", "risk_db"]}
        )
        
        # Agent action: fetching data
        logger.action(
            "fetch_user_data",
            details={
                "user_id": user_id,
                "operation": "fetch_user_profile",
                "data_sources": ["user_db", "transaction_history", "risk_db"]
            }
        )
        
        with self.client.infer("user-profile-model", "internal_db") as model_call:
            # Simulate data fetching with realistic timing
            fetch_start = time.time()
            
            # Simulate database query latency
            time.sleep(random.uniform(0.05, 0.15))
            
            # Generate realistic user profile
            profile = UserProfile(
                user_id=user_id,
                account_age_days=random.randint(30, 1000),
                avg_transaction_amount=random.uniform(50, 500),
                transaction_count=random.randint(10, 1000),
                risk_score=random.uniform(0.1, 0.9),
                location_history=[f"City_{i}" for i in range(random.randint(1, 5))],
                flagged_previously=random.choice([True, False])
            )
            
            fetch_duration = time.time() - fetch_start
            
            # Log detailed metrics
            self.client.metric("data_fetch_duration_ms", fetch_duration * 1000, "ms", 
                             tags={"agent": self.agent_name, "data_type": "user_profile"})
            self.client.metric("user_risk_score", profile.risk_score, "score",
                             tags={"user_id": user_id, "agent": self.agent_name})
            self.client.metric("user_account_age_days", profile.account_age_days, "days",
                             tags={"user_id": user_id})
            
            # Set model call details
            model_call.input_token_count = 25
            model_call.output_token_count = 150
            model_call.total_tokens = 175
            
            # Agent observation about the data retrieved
            logger.observation(
                f"User profile retrieved successfully for user {user_id}",
                source="user_db",
                confidence=random.uniform(0.8, 1.0)
            )
            
            # Log success with agent logger
            logger.info(
                "User profile retrieved successfully",
                {
                    "user_id": user_id,
                    "profile_completeness": "100%",
                    "data_quality_score": random.uniform(0.8, 1.0),
                    "fetch_duration_ms": fetch_duration * 1000,
                    "risk_indicators_found": len([f for f in [profile.flagged_previously, profile.risk_score > 0.7] if f])
                }
            )
            
            return profile
    
    def fetch_transaction_context(self, transaction: Transaction, run_id: str) -> Dict[str, Any]:
        """Fetch additional context about the transaction."""
        
        logger = self.logger.with_context(run_id=run_id)
        
        # Agent thinking about context enrichment
        logger.thinking(
            f"Enriching transaction {transaction.transaction_id} with additional context data",
            context={"transaction_id": transaction.transaction_id}
        )
        
        context_start = time.time()
        
        # Agent action: enriching context
        logger.action(
            "enrich_transaction_context",
            details={
                "transaction_id": transaction.transaction_id,
                "amount": transaction.amount,
                "merchant": transaction.merchant,
                "location": transaction.location
            }
        )
        
        # Simulate context enrichment
        time.sleep(random.uniform(0.03, 0.08))
        
        context = {
            "merchant_risk_score": random.uniform(0.1, 0.8),
            "location_risk_score": random.uniform(0.1, 0.9),
            "time_of_day_risk": random.uniform(0.1, 0.7),
            "amount_percentile": random.uniform(0.1, 0.95),
            "velocity_check": {
                "transactions_last_hour": random.randint(0, 5),
                "amount_last_hour": random.uniform(0, 1000)
            },
            "device_fingerprint": f"device_{random.randint(1000, 9999)}",
            "ip_reputation": random.uniform(0.2, 1.0)
        }
        
        context_duration = time.time() - context_start
        
        # Log context metrics
        self.client.metric("context_enrichment_duration_ms", context_duration * 1000, "ms")
        self.client.metric("merchant_risk_score", context["merchant_risk_score"], "score")
        self.client.metric("location_risk_score", context["location_risk_score"], "score")
        self.client.metric("transaction_velocity", context["velocity_check"]["transactions_last_hour"], "count")
        
        return context


class RiskAnalysisAgent:
    """Agent responsible for analyzing fraud risk and making decisions."""
    
    def __init__(self, client: TelemetryClient):
        self.client = client
        self.agent_name = "Risk Analysis Agent"
        self.agent_role = "decision-maker"
        # Use get_agent_logger for agent-specific logging with role
        self.logger = get_agent_logger(self.agent_name, client=client, role=self.agent_role)
        
    def analyze_risk(self, transaction: Transaction, user_profile: UserProfile, 
                    context: Dict[str, Any], run_id: str) -> RiskAssessment:
        """Perform comprehensive risk analysis."""
        
        logger = self.logger.with_context(run_id=run_id)
        
        # Agent thinking about risk analysis
        logger.thinking(
            f"Analyzing fraud risk for transaction {transaction.transaction_id}. "
            f"Amount: ${transaction.amount}, User risk history: {user_profile.risk_score:.2f}",
            context={
                "transaction_id": transaction.transaction_id,
                "amount": transaction.amount,
                "user_risk_score": user_profile.risk_score
            }
        )
        
        with self.client.infer("fraud-detection-model-v2", "ml_engine") as model_call:
            analysis_start = time.time()
            
            # Agent action: performing risk analysis
            logger.action(
                "analyze_fraud_risk",
                details={
                    "transaction_id": transaction.transaction_id,
                    "user_id": transaction.user_id,
                    "amount": transaction.amount,
                    "analysis_version": "v2.1",
                    "features_count": 15
                }
            )
            
            # Simulate ML model inference
            time.sleep(random.uniform(0.1, 0.3))
            
            # Calculate risk factors
            risk_factors = []
            risk_score = 0.0
            
            # Amount-based risk
            if transaction.amount > user_profile.avg_transaction_amount * 3:
                risk_factors.append("unusual_amount")
                risk_score += 0.3
            
            # User risk history
            if user_profile.flagged_previously:
                risk_factors.append("previous_flags")
                risk_score += 0.4
            
            # Location risk
            if context["location_risk_score"] > 0.7:
                risk_factors.append("high_risk_location")
                risk_score += 0.2
            
            # Velocity risk
            if context["velocity_check"]["transactions_last_hour"] > 3:
                risk_factors.append("high_velocity")
                risk_score += 0.3
            
            # Merchant risk
            if context["merchant_risk_score"] > 0.6:
                risk_factors.append("risky_merchant")
                risk_score += 0.2
            
            # Time-based risk
            hour = transaction.timestamp.hour
            if hour < 6 or hour > 22:  # Late night transactions
                risk_factors.append("unusual_time")
                risk_score += 0.1
            
            # Normalize risk score
            risk_score = min(risk_score, 1.0)
            
            # Determine risk level and decision
            if risk_score < 0.3:
                risk_level = RiskLevel.LOW
                decision = "approve"
                confidence = 0.95
            elif risk_score < 0.6:
                risk_level = RiskLevel.MEDIUM
                decision = "flag"
                confidence = 0.80
            elif risk_score < 0.8:
                risk_level = RiskLevel.HIGH
                decision = "flag"
                confidence = 0.85
            else:
                risk_level = RiskLevel.CRITICAL
                decision = "block"
                confidence = 0.92
            
            assessment = RiskAssessment(
                transaction_id=transaction.transaction_id,
                risk_level=risk_level,
                risk_score=risk_score,
                factors=risk_factors,
                decision=decision,
                confidence=confidence
            )
            
            analysis_duration = time.time() - analysis_start
            
            # Log comprehensive metrics
            self.client.metric("risk_analysis_duration_ms", analysis_duration * 1000, "ms")
            self.client.metric("risk_score", risk_score, "score", 
                             tags={"transaction_id": transaction.transaction_id})
            self.client.metric("risk_factors_count", len(risk_factors), "count")
            self.client.metric("decision_confidence", confidence, "score")
            
            # Set model call details
            model_call.input_token_count = 200
            model_call.output_token_count = 50
            model_call.total_tokens = 250
            
            # Agent decision with reasoning
            logger.decision(
                decision,
                reasoning=f"Risk score {risk_score:.3f} with factors: {', '.join(risk_factors)}. "
                        f"Confidence: {confidence:.2f}",
                options={
                    "risk_level": risk_level.value,
                    "risk_score": risk_score,
                    "confidence": confidence,
                    "factors": risk_factors,
                    "alternatives": ["approve", "flag", "block"]
                }
            )
            
            # Log the analysis result
            if decision == "approve":
                logger.info(
                    f"Risk analysis completed: {decision.upper()} ({risk_level.value})",
                    {
                        "transaction_id": transaction.transaction_id,
                        "decision": decision,
                        "risk_level": risk_level.value,
                        "risk_score": risk_score,
                        "confidence": confidence,
                        "factors": risk_factors,
                        "analysis_duration_ms": analysis_duration * 1000,
                        "model_version": "fraud-detection-v2.1"
                    }
                )
            else:
                logger.warning(
                    f"Risk analysis completed: {decision.upper()} ({risk_level.value})",
                    {
                        "transaction_id": transaction.transaction_id,
                        "decision": decision,
                        "risk_level": risk_level.value,
                        "risk_score": risk_score,
                        "confidence": confidence,
                        "factors": risk_factors,
                        "analysis_duration_ms": analysis_duration * 1000,
                        "model_version": "fraud-detection-v2.1"
                    }
                )
            
            return assessment
    
    def flag_transaction(self, assessment: RiskAssessment, run_id: str) -> Dict[str, Any]:
        """Flag a transaction for manual review."""
        
        logger = self.logger.with_context(run_id=run_id)
        
        # Agent decision to flag
        logger.decision(
            "flag_for_review",
            reasoning=f"Transaction has {assessment.risk_level.value} risk level with score {assessment.risk_score:.3f}",
            options={"queue": "manual_review", "priority": "high" if assessment.risk_level == RiskLevel.CRITICAL else "medium"}
        )
        
        # Agent action: flagging transaction
        logger.action(
            "flag_transaction",
            details={
                "transaction_id": assessment.transaction_id,
                "risk_score": assessment.risk_score,
                "risk_level": assessment.risk_level.value,
                "factors": assessment.factors,
                "queue": "manual_review"
            }
        )
        
        self.client.metric("transactions_flagged", 1, "count")
        
        return {
            "status": "flagged",
            "queue": "manual_review",
            "priority": "high" if assessment.risk_level == RiskLevel.CRITICAL else "medium"
        }
    
    def approve_transaction(self, assessment: RiskAssessment, run_id: str) -> Dict[str, Any]:
        """Approve a low-risk transaction."""
        
        logger = self.logger.with_context(run_id=run_id)
        
        # Agent decision to approve
        logger.decision(
            "approve_transaction",
            reasoning=f"Low risk score {assessment.risk_score:.3f} with high confidence {assessment.confidence:.2f}",
            options={"auto_approved": True, "requires_review": False}
        )
        
        # Agent action: approving transaction
        logger.action(
            "approve_transaction",
            details={
                "transaction_id": assessment.transaction_id,
                "risk_score": assessment.risk_score,
                "auto_approved": True
            }
        )
        
        self.client.metric("transactions_approved", 1, "count")
        
        return {
            "status": "approved",
            "processing_time_ms": random.uniform(50, 100)
        }


class AlertManagementAgent:
    """Agent responsible for managing alerts and notifications."""
    
    def __init__(self, client: TelemetryClient):
        self.client = client
        self.agent_name = "Alert Management Agent"
        self.agent_role = "notification"
        # Use get_agent_logger for agent-specific logging with role
        self.logger = get_agent_logger(self.agent_name, client=client, role=self.agent_role)
        
    def send_alert(self, assessment: RiskAssessment, transaction: Transaction, run_id: str) -> Dict[str, Any]:
        """Send appropriate alerts based on risk assessment."""
        
        logger = self.logger.with_context(run_id=run_id)
        
        # Agent thinking about alert strategy
        logger.thinking(
            f"Determining alert channels for {assessment.risk_level.value} risk transaction {transaction.transaction_id}",
            context={"risk_level": assessment.risk_level.value, "risk_score": assessment.risk_score}
        )
        
        alert_start = time.time()
        
        # Determine alert channels and urgency
        channels = []
        if assessment.risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL]:
            channels.extend(["email", "sms", "slack"])
        elif assessment.risk_level == RiskLevel.MEDIUM:
            channels.extend(["email", "dashboard"])
        else:
            channels.append("dashboard")
        
        # Agent decision on alert channels
        logger.decision(
            "select_alert_channels",
            reasoning=f"Risk level {assessment.risk_level.value} requires {len(channels)} notification channels",
            options={"channels": channels, "urgency": "high" if assessment.risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL] else "medium"}
        )
        
        # Agent action: sending alerts
        logger.action(
            "send_fraud_alert",
            details={
                "transaction_id": transaction.transaction_id,
                "risk_level": assessment.risk_level.value,
                "risk_score": assessment.risk_score,
                "channels": channels,
                "user_id": transaction.user_id,
                "amount": transaction.amount
            }
        )
        
        # Simulate alert sending
        for channel in channels:
            time.sleep(random.uniform(0.02, 0.05))  # Simulate network latency
            
            self.client.metric("alerts_sent", 1, "count", 
                             tags={"channel": channel, "risk_level": assessment.risk_level.value})
            
            # Agent observation about alert delivery
            logger.observation(
                f"Alert successfully sent via {channel}",
                source=channel,
                confidence=0.95
            )
        
        alert_duration = time.time() - alert_start
        self.client.metric("alert_processing_duration_ms", alert_duration * 1000, "ms")
        
        return {
            "alerts_sent": len(channels),
            "channels": channels,
            "processing_time_ms": alert_duration * 1000
        }
    
    def update_dashboard(self, assessment: RiskAssessment, run_id: str) -> None:
        """Update monitoring dashboard with latest metrics."""
        
        logger = self.logger.with_context(run_id=run_id)
        
        # Agent action: updating dashboard
        logger.action(
            "update_dashboard",
            details={
                "transaction_id": assessment.transaction_id,
                "dashboard_widgets": ["risk_score_trend", "decision_summary", "alert_count"],
                "update_type": "real_time"
            }
        )
        
        self.client.metric("dashboard_updates", 1, "count")


class FraudDetectionPipeline:
    """Main pipeline orchestrating the fraud detection process."""
    
    def __init__(self):
        # Initialize telemetry client
        self.client = TelemetryClient(
            agent_id="FraudDetectionSystem",
            metadata={
                "system": "fraud_detection",
                "version": "2.1.0",
                "environment": "production",
                "pipeline_id": "fraud_pipeline_001"
            },
            default_tags={
                "system": "fraud_detection",
                "pipeline": "main"
            }
        )
        
        # Add comprehensive logging
        # Get project name from environment
        project_name = os.environ.get("ABIDEX_PROJECT_NAME", "fraud_detection")
        
        # Resolve log file path using utility function
        log_filename = f"fraud_detection_logs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jsonl"
        log_file = str(resolve_workflow_log_path(project_name, log_filename))
        self.client.add_sink(JSONLSink(log_file))
        
        # Initialize agents
        self.data_agent = DataCollectionAgent(self.client)
        self.risk_agent = RiskAnalysisAgent(self.client)
        self.alert_agent = AlertManagementAgent(self.client)
        
        print(f" Fraud Detection Pipeline initialized")
        print(f" Telemetry logging to: {log_file}")
    
    def process_transaction(self, transaction: Transaction) -> Dict[str, Any]:
        """Process a single transaction through the complete fraud detection pipeline."""
        
        with AgentRun(f"fraud_check_{transaction.transaction_id}", client=self.client) as run:
            run.add_data("transaction_id", transaction.transaction_id)
            run.add_data("user_id", transaction.user_id)
            run.add_data("amount", transaction.amount)
            run.add_data("merchant", transaction.merchant)
            run.add_data("pipeline_version", "2.1.0")
            
            pipeline_start = time.time()
            
            try:
                # Step 1: Data Collection
                self.client.log(
                    f"Starting fraud detection pipeline for transaction {transaction.transaction_id}",
                    level="info",
                    data={
                        "transaction_id": transaction.transaction_id,
                        "pipeline_step": "initialization",
                        "user_id": transaction.user_id,
                        "amount": transaction.amount
                    },
                    tags={"pipeline": "fraud_detection", "step": "start"},
                    run_id=run.run_id
                )
                
                # Fetch user profile
                user_profile = self.data_agent.fetch_user_data(transaction.user_id, run.run_id)
                
                # Fetch transaction context
                context = self.data_agent.fetch_transaction_context(transaction, run.run_id)
                
                # Step 2: Risk Analysis
                assessment = self.risk_agent.analyze_risk(transaction, user_profile, context, run.run_id)
                
                # Step 3: Decision Processing
                if assessment.decision == "approve":
                    result = self.risk_agent.approve_transaction(assessment, run.run_id)
                elif assessment.decision == "flag":
                    result = self.risk_agent.flag_transaction(assessment, run.run_id)
                else:  # block
                    result = {"status": "blocked", "reason": "high_risk"}
                    self.client.log(
                        f"Transaction {transaction.transaction_id} BLOCKED",
                        level="error",
                        data={
                            "transaction_id": transaction.transaction_id,
                            "risk_score": assessment.risk_score,
                            "factors": assessment.factors
                        },
                        tags={"decision": "blocked"},
                        run_id=run.run_id
                    )
                
                # Step 4: Alert Management
                if assessment.decision in ["flag", "block"]:
                    alert_result = self.alert_agent.send_alert(assessment, transaction, run.run_id)
                    result["alerts"] = alert_result
                
                # Always update dashboard
                self.alert_agent.update_dashboard(assessment, run.run_id)
                
                pipeline_duration = time.time() - pipeline_start
                
                # Log pipeline completion
                self.client.log(
                    f"Pipeline completed for transaction {transaction.transaction_id}",
                    level="info",
                    data={
                        "transaction_id": transaction.transaction_id,
                        "final_decision": assessment.decision,
                        "risk_score": assessment.risk_score,
                        "pipeline_duration_ms": pipeline_duration * 1000,
                        "success": True
                    },
                    tags={"pipeline": "fraud_detection", "step": "complete"},
                    run_id=run.run_id
                )
                
                # Record pipeline metrics
                self.client.metric("pipeline_duration_ms", pipeline_duration * 1000, "ms")
                self.client.metric("pipeline_success", 1, "count")
                
                run.add_data("final_decision", assessment.decision)
                run.add_data("risk_score", assessment.risk_score)
                run.add_data("processing_duration_ms", pipeline_duration * 1000)
                
                return {
                    "transaction_id": transaction.transaction_id,
                    "decision": assessment.decision,
                    "risk_assessment": assessment,
                    "processing_result": result,
                    "pipeline_duration_ms": pipeline_duration * 1000
                }
                
            except Exception as e:
                pipeline_duration = time.time() - pipeline_start
                
                self.client.error(
                    e,
                    context={
                        "transaction_id": transaction.transaction_id,
                        "pipeline_step": "unknown",
                        "duration_ms": pipeline_duration * 1000
                    },
                    run_id=run.run_id
                )
                
                self.client.metric("pipeline_errors", 1, "count")
                
                run.add_data("error", str(e))
                run.add_data("success", False)
                
                raise
    
    def run_demo(self, num_transactions: Optional[int] = None):
        """Run a demo with multiple transactions to generate comprehensive telemetry data."""
        
        # Get transaction count from environment or use default
        if num_transactions is None:
            num_transactions = int(os.environ.get('FRAUD_DEMO_TRANSACTIONS', 25))
        
        print(f"\n Starting Fraud Detection Demo with {num_transactions} transactions")
        print("=" * 60)
        
        # Generate sample transactions
        transactions = self._generate_sample_transactions(num_transactions)
        
        results = []
        start_time = time.time()
        
        for i, transaction in enumerate(transactions, 1):
            print(f"\n[{i}/{num_transactions}] Processing transaction {transaction.transaction_id}")
            print(f"  Amount: ${transaction.amount:.2f} | Merchant: {transaction.merchant} | User: {transaction.user_id}")
            
            try:
                result = self.process_transaction(transaction)
                results.append(result)
                
                decision = result['decision']
                risk_score = result['risk_assessment'].risk_score
                
                # Color-coded output
                if decision == "approve":
                    print(f"   APPROVED (Risk: {risk_score:.2f})")
                elif decision == "flag":
                    print(f"    FLAGGED (Risk: {risk_score:.2f})")
                else:
                    print(f"   BLOCKED (Risk: {risk_score:.2f})")
                
                # Add small delay to simulate realistic processing
                time.sleep(random.uniform(0.1, 0.3))
                
            except Exception as e:
                print(f"   ERROR: {str(e)}")
                results.append({"error": str(e), "transaction_id": transaction.transaction_id})
        
        total_duration = time.time() - start_time
        
        # Summary statistics
        successful_results = [r for r in results if "error" not in r]
        decisions = [r['decision'] for r in successful_results]
        
        print(f"\n DEMO SUMMARY")
        print("=" * 30)
        print(f"Total Transactions: {num_transactions}")
        print(f"Successful: {len(successful_results)}")
        print(f"Errors: {num_transactions - len(successful_results)}")
        print(f"Approved: {decisions.count('approve')}")
        print(f"Flagged: {decisions.count('flag')}")
        print(f"Blocked: {decisions.count('block')}")
        print(f"Total Duration: {total_duration:.2f}s")
        print(f"Avg per Transaction: {total_duration/num_transactions:.2f}s")
        
        # Final metrics
        self.client.metric("demo_total_transactions", num_transactions, "count")
        self.client.metric("demo_duration_seconds", total_duration, "seconds")
        self.client.metric("demo_throughput_tps", num_transactions / total_duration, "tps")
        
        # Flush all telemetry
        self.client.flush()
        self.client.close()
        
        print(f"\n Demo completed! Check the generated log files for detailed telemetry data.")
        
        return results
    
    def _generate_sample_transactions(self, count: int) -> List[Transaction]:
        """Generate realistic sample transactions for the demo."""
        
        merchants = [
            "Amazon", "Walmart", "Target", "Starbucks", "McDonald's", 
            "Shell", "Uber", "Netflix", "Steam", "PayPal",
            "SuspiciousMerchant", "HighRiskStore", "UnknownVendor"
        ]
        
        locations = [
            "New York, NY", "Los Angeles, CA", "Chicago, IL", "Houston, TX",
            "Phoenix, AZ", "Philadelphia, PA", "San Antonio, TX", "San Diego, CA",
            "Unknown Location", "High Risk Country", "Blacklisted Region"
        ]
        
        payment_methods = ["credit_card", "debit_card", "digital_wallet", "bank_transfer"]
        
        transactions = []
        
        for i in range(count):
            # Create some high-risk transactions intentionally
            if i % 7 == 0:  # Every 7th transaction is high risk
                amount = random.uniform(5000, 15000)  # Large amount
                merchant = random.choice(["SuspiciousMerchant", "HighRiskStore", "UnknownVendor"])
                location = random.choice(["Unknown Location", "High Risk Country", "Blacklisted Region"])
            else:
                amount = random.uniform(10, 500)  # Normal amount
                merchant = random.choice(merchants[:10])  # Safe merchants
                location = random.choice(locations[:8])  # Safe locations
            
            transaction = Transaction(
                transaction_id=f"txn_{datetime.now().strftime('%Y%m%d')}_{i+1:04d}",
                user_id=f"user_{random.randint(1000, 9999)}",
                amount=amount,
                merchant=merchant,
                location=location,
                timestamp=datetime.now() - timedelta(minutes=random.randint(0, 60)),
                payment_method=random.choice(payment_methods)
            )
            
            transactions.append(transaction)
        
        return transactions


def main():
    """Main demo function."""
    print(" FRAUD DETECTION PIPELINE DEMO")
    print("=" * 50)
    print("This demo showcases a complete fraud detection system with:")
    print("• Data Collection Agent - Fetches user profiles and transaction context")
    print("• Risk Analysis Agent - Analyzes fraud risk and makes decisions") 
    print("• Alert Management Agent - Handles notifications and alerts")
    print("• Comprehensive telemetry with OpenTelemetry-style metrics")
    
    # Initialize and run the pipeline
    pipeline = FraudDetectionPipeline()
    
    # Run demo with 25 transactions
    results = pipeline.run_demo(25)
    
    print("\n Next Steps:")
    print("1. Open the generated fraud_detection_logs_*.jsonl file")
    print("2. Use the Jupyter notebook to analyze all the telemetry data")
    print("3. Explore agent performance, risk patterns, and system metrics")
    
    # Force immediate exit to prevent hanging
    import os
    os._exit(0)


if __name__ == "__main__":
    main()
