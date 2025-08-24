"""
Utility script for analyzing user feedback on RAG responses.
"""
import json
import argparse
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Any, Tuple
from collections import Counter, defaultdict
import statistics


def load_feedback_logs(file_path: str) -> List[Dict[str, Any]]:
    """Load feedback JSONL log file and return list of feedback entries."""
    feedback_logs = []
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    feedback_logs.append(json.loads(line))
    except FileNotFoundError:
        print(f"Feedback log file not found: {file_path}")
    except Exception as e:
        print(f"Error reading feedback log file: {e}")
    
    return feedback_logs


def load_interaction_logs(file_path: str) -> Dict[int, Dict[str, Any]]:
    """Load interaction logs and index by message_id for correlation."""
    interactions = {}
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    interaction = json.loads(line)
                    if interaction.get('message_id'):
                        interactions[interaction['message_id']] = interaction
    except FileNotFoundError:
        print(f"Interaction log file not found: {file_path}")
    except Exception as e:
        print(f"Error reading interaction log file: {e}")
    
    return interactions


def analyze_feedback(feedback_logs: List[Dict[str, Any]], interaction_logs: Dict[int, Dict[str, Any]] = None) -> Dict[str, Any]:
    """Analyze feedback logs and return comprehensive statistics."""
    if not feedback_logs:
        return {"error": "No feedback data to analyze"}
    
    total_feedback = len(feedback_logs)
    
    # Basic feedback distribution
    feedback_counts = Counter(log.get("feedback_type") for log in feedback_logs)
    positive_feedback = feedback_counts.get("up", 0)
    negative_feedback = feedback_counts.get("down", 0)
    
    satisfaction_rate = (positive_feedback / total_feedback * 100) if total_feedback > 0 else 0
    
    # Time-based analysis
    feedback_by_hour = defaultdict(list)
    feedback_by_day = defaultdict(list)
    
    for log in feedback_logs:
        timestamp = log.get("timestamp")
        if timestamp:
            try:
                dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                hour = dt.hour
                day = dt.strftime('%Y-%m-%d')
                
                feedback_by_hour[hour].append(log)
                feedback_by_day[day].append(log)
            except:
                continue
    
    # Response quality analysis (if interaction logs available)
    quality_analysis = {}
    if interaction_logs:
        feedback_with_context = []
        
        for feedback in feedback_logs:
            message_id = feedback.get("message_id")
            if message_id in interaction_logs:
                interaction = interaction_logs[message_id]
                
                combined_data = {
                    **feedback,
                    "interaction_latency": interaction.get("latency_ms"),
                    "num_retrieved": interaction.get("num_retrieved", 0),
                    "retrieval_latency": interaction.get("retrieval_latency_ms"),
                    "generation_latency": interaction.get("generation_latency_ms"),
                    "model_name": interaction.get("model_name"),
                    "query_length": len(interaction.get("user_query", "")),
                    "response_length": len(interaction.get("response", ""))
                }
                feedback_with_context.append(combined_data)
        
        if feedback_with_context:
            # Analyze patterns in positive vs negative feedback
            positive_feedback_data = [f for f in feedback_with_context if f.get("feedback_type") == "up"]
            negative_feedback_data = [f for f in feedback_with_context if f.get("feedback_type") == "down"]
            
            quality_analysis = {
                "positive_feedback_patterns": analyze_feedback_patterns(positive_feedback_data),
                "negative_feedback_patterns": analyze_feedback_patterns(negative_feedback_data),
                "performance_correlation": analyze_performance_correlation(feedback_with_context)
            }
    
    # User behavior analysis
    user_feedback_patterns = defaultdict(list)
    for log in feedback_logs:
        user_id = log.get("user_id", "anonymous")
        user_feedback_patterns[user_id].append(log.get("feedback_type"))
    
    # Most problematic queries (negative feedback)
    problematic_queries = []
    for log in feedback_logs:
        if log.get("feedback_type") == "down":
            query = log.get("original_query", "")[:100]  # Truncate for display
            problematic_queries.append({
                "timestamp": log.get("timestamp"),
                "query": query,
                "message_id": log.get("message_id")
            })
    
    # Time range
    timestamps = [log.get("timestamp") for log in feedback_logs if log.get("timestamp")]
    time_range = None
    if timestamps:
        try:
            first_time = min(timestamps)
            last_time = max(timestamps)
            time_range = f"{first_time} to {last_time}"
        except:
            pass
    
    analysis = {
        "summary": {
            "total_feedback": total_feedback,
            "positive_feedback": positive_feedback,
            "negative_feedback": negative_feedback,
            "satisfaction_rate_percent": round(satisfaction_rate, 2),
            "time_range": time_range
        },
        "feedback_distribution": dict(feedback_counts),
        "temporal_patterns": {
            "feedback_by_hour": {hour: len(logs) for hour, logs in feedback_by_hour.items()},
            "feedback_by_day": {day: len(logs) for day, logs in feedback_by_day.items()},
            "peak_feedback_hour": max(feedback_by_hour.keys(), key=lambda h: len(feedback_by_hour[h])) if feedback_by_hour else None
        },
        "user_patterns": {
            "unique_users": len(user_feedback_patterns),
            "users_with_mixed_feedback": sum(1 for patterns in user_feedback_patterns.values() 
                                           if "up" in patterns and "down" in patterns),
            "most_active_user": max(user_feedback_patterns.keys(), 
                                  key=lambda u: len(user_feedback_patterns[u])) if user_feedback_patterns else None
        },
        "quality_analysis": quality_analysis,
        "problematic_queries": problematic_queries[:10],  # Top 10 most recent
        "recommendations": generate_recommendations(feedback_logs, quality_analysis)
    }
    
    return analysis


def analyze_feedback_patterns(feedback_data: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Analyze patterns in feedback data."""
    if not feedback_data:
        return {}
    
    latencies = [f.get("interaction_latency", 0) for f in feedback_data if f.get("interaction_latency")]
    retrieval_counts = [f.get("num_retrieved", 0) for f in feedback_data]
    query_lengths = [f.get("query_length", 0) for f in feedback_data if f.get("query_length")]
    response_lengths = [f.get("response_length", 0) for f in feedback_data if f.get("response_length")]
    
    return {
        "avg_latency_ms": round(statistics.mean(latencies), 2) if latencies else 0,
        "avg_retrieval_count": round(statistics.mean(retrieval_counts), 2) if retrieval_counts else 0,
        "avg_query_length": round(statistics.mean(query_lengths), 2) if query_lengths else 0,
        "avg_response_length": round(statistics.mean(response_lengths), 2) if response_lengths else 0,
        "sample_count": len(feedback_data)
    }


def analyze_performance_correlation(feedback_data: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Analyze correlation between performance metrics and feedback."""
    if len(feedback_data) < 2:
        return {"error": "Insufficient data for correlation analysis"}
    
    positive_latencies = [f.get("interaction_latency", 0) for f in feedback_data 
                         if f.get("feedback_type") == "up" and f.get("interaction_latency")]
    negative_latencies = [f.get("interaction_latency", 0) for f in feedback_data 
                         if f.get("feedback_type") == "down" and f.get("interaction_latency")]
    
    positive_retrievals = [f.get("num_retrieved", 0) for f in feedback_data 
                          if f.get("feedback_type") == "up"]
    negative_retrievals = [f.get("num_retrieved", 0) for f in feedback_data 
                          if f.get("feedback_type") == "down"]
    
    return {
        "latency_impact": {
            "positive_avg_latency": round(statistics.mean(positive_latencies), 2) if positive_latencies else 0,
            "negative_avg_latency": round(statistics.mean(negative_latencies), 2) if negative_latencies else 0,
            "latency_difference": round(statistics.mean(negative_latencies) - statistics.mean(positive_latencies), 2) 
                                if positive_latencies and negative_latencies else 0
        },
        "retrieval_impact": {
            "positive_avg_retrievals": round(statistics.mean(positive_retrievals), 2) if positive_retrievals else 0,
            "negative_avg_retrievals": round(statistics.mean(negative_retrievals), 2) if negative_retrievals else 0,
            "retrieval_difference": round(statistics.mean(negative_retrievals) - statistics.mean(positive_retrievals), 2) 
                                  if positive_retrievals and negative_retrievals else 0
        }
    }


def generate_recommendations(feedback_logs: List[Dict[str, Any]], quality_analysis: Dict[str, Any]) -> List[str]:
    """Generate actionable recommendations based on feedback analysis."""
    recommendations = []
    
    if not feedback_logs:
        return ["No feedback data available for recommendations"]
    
    total_feedback = len(feedback_logs)
    negative_count = sum(1 for f in feedback_logs if f.get("feedback_type") == "down")
    negative_rate = negative_count / total_feedback * 100
    
    if negative_rate > 30:
        recommendations.append("🚨 High negative feedback rate (>30%). Consider reviewing response quality and relevance.")
    elif negative_rate > 20:
        recommendations.append("⚠️ Moderate negative feedback rate (>20%). Monitor response patterns closely.")
    else:
        recommendations.append("✅ Acceptable negative feedback rate (<20%). Continue current approach.")
    
    # Performance-based recommendations
    if quality_analysis and "performance_correlation" in quality_analysis:
        perf = quality_analysis["performance_correlation"]
        
        if "latency_impact" in perf:
            latency_diff = perf["latency_impact"].get("latency_difference", 0)
            if latency_diff > 500:  # Negative feedback has 500ms+ higher latency
                recommendations.append("⏱️ Negative feedback correlates with high latency. Consider optimizing response time.")
        
        if "retrieval_impact" in perf:
            retrieval_diff = perf["retrieval_impact"].get("retrieval_difference", 0)
            if retrieval_diff < -0.5:  # Negative feedback has fewer retrievals
                recommendations.append("📚 Negative feedback correlates with fewer retrieved documents. Consider improving retrieval relevance.")
    
    # Temporal recommendations
    if total_feedback < 10:
        recommendations.append("📊 Low feedback volume. Consider encouraging more user feedback to improve insights.")
    
    return recommendations


def print_feedback_analysis(analysis: Dict[str, Any]):
    """Print the feedback analysis in a readable format."""
    print("=" * 70)
    print("USER FEEDBACK ANALYSIS")
    print("=" * 70)
    
    if "error" in analysis:
        print(f"Error: {analysis['error']}")
        return
    
    # Summary
    summary = analysis["summary"]
    print(f"\n📊 FEEDBACK SUMMARY")
    print(f"   Total Feedback: {summary['total_feedback']}")
    print(f"   👍 Positive: {summary['positive_feedback']} ({summary['satisfaction_rate_percent']}%)")
    print(f"   👎 Negative: {summary['negative_feedback']} ({100 - summary['satisfaction_rate_percent']:.1f}%)")
    print(f"   Time Range: {summary['time_range']}")
    
    # Distribution
    print(f"\n📈 FEEDBACK DISTRIBUTION")
    for feedback_type, count in analysis["feedback_distribution"].items():
        print(f"   {feedback_type}: {count}")
    
    # Temporal patterns
    temporal = analysis["temporal_patterns"]
    print(f"\n⏰ TEMPORAL PATTERNS")
    print(f"   Peak Feedback Hour: {temporal['peak_feedback_hour']}:00" if temporal['peak_feedback_hour'] else "N/A")
    print(f"   Most Active Days: {', '.join(sorted(temporal['feedback_by_day'].keys())[-3:])}")
    
    # User patterns
    user_patterns = analysis["user_patterns"]
    print(f"\n👥 USER PATTERNS")
    print(f"   Unique Users: {user_patterns['unique_users']}")
    print(f"   Users with Mixed Feedback: {user_patterns['users_with_mixed_feedback']}")
    print(f"   Most Active User: {user_patterns['most_active_user']}")
    
    # Quality analysis
    if analysis["quality_analysis"]:
        quality = analysis["quality_analysis"]
        print(f"\n🎯 QUALITY ANALYSIS")
        
        if "positive_feedback_patterns" in quality:
            pos = quality["positive_feedback_patterns"]
            print(f"   Positive Feedback Patterns:")
            print(f"     Avg Latency: {pos.get('avg_latency_ms', 0)}ms")
            print(f"     Avg Retrievals: {pos.get('avg_retrieval_count', 0)}")
            print(f"     Sample Size: {pos.get('sample_count', 0)}")
        
        if "negative_feedback_patterns" in quality:
            neg = quality["negative_feedback_patterns"]
            print(f"   Negative Feedback Patterns:")
            print(f"     Avg Latency: {neg.get('avg_latency_ms', 0)}ms")
            print(f"     Avg Retrievals: {neg.get('avg_retrieval_count', 0)}")
            print(f"     Sample Size: {neg.get('sample_count', 0)}")
        
        if "performance_correlation" in quality:
            perf = quality["performance_correlation"]
            if "latency_impact" in perf:
                lat = perf["latency_impact"]
                print(f"   Performance Correlation:")
                print(f"     Latency Impact: {lat.get('latency_difference', 0)}ms difference")
    
    # Problematic queries
    if analysis["problematic_queries"]:
        print(f"\n❌ RECENT PROBLEMATIC QUERIES")
        for i, query in enumerate(analysis["problematic_queries"][:5], 1):
            print(f"   {i}. {query['timestamp'][:19]}: {query['query']}")
    
    # Recommendations
    if analysis["recommendations"]:
        print(f"\n💡 RECOMMENDATIONS")
        for i, rec in enumerate(analysis["recommendations"], 1):
            print(f"   {i}. {rec}")


def main():
    parser = argparse.ArgumentParser(description="Analyze user feedback on RAG responses")
    parser.add_argument(
        "--feedback-log", 
        default="logs/feedback_interactions.jsonl",
        help="Path to the feedback JSONL log file (default: logs/feedback_interactions.jsonl)"
    )
    parser.add_argument(
        "--interaction-log", 
        default="logs/rag_interactions.jsonl",
        help="Path to the interaction JSONL log file for correlation (default: logs/rag_interactions.jsonl)"
    )
    parser.add_argument(
        "--output",
        choices=["console", "json"],
        default="console",
        help="Output format (default: console)"
    )
    parser.add_argument(
        "--correlate",
        action="store_true",
        help="Correlate feedback with interaction data for deeper analysis"
    )
    
    args = parser.parse_args()
    
    # Load feedback logs
    feedback_logs = load_feedback_logs(args.feedback_log)
    
    if not feedback_logs:
        print("No feedback logs found or file doesn't exist yet.")
        return
    
    # Load interaction logs for correlation if requested
    interaction_logs = {}
    if args.correlate:
        interaction_logs = load_interaction_logs(args.interaction_log)
        print(f"Loaded {len(interaction_logs)} interaction records for correlation")
    
    # Analyze feedback
    analysis = analyze_feedback(feedback_logs, interaction_logs if args.correlate else None)
    
    # Output results
    if args.output == "json":
        print(json.dumps(analysis, indent=2))
    else:
        print_feedback_analysis(analysis)


if __name__ == "__main__":
    main()
