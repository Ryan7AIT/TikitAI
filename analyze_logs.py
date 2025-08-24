"""
Utility script for analyzing RAG interaction logs.
"""
import json
import argparse
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any
import statistics


def load_jsonl_logs(file_path: str) -> List[Dict[str, Any]]:
    """Load JSONL log file and return list of log entries."""
    logs = []
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    logs.append(json.loads(line))
    except FileNotFoundError:
        print(f"Log file not found: {file_path}")
    except Exception as e:
        print(f"Error reading log file: {e}")
    
    return logs


def analyze_logs(logs: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Analyze the logs and return summary statistics."""
    if not logs:
        return {"error": "No logs to analyze"}
    
    # Basic stats
    total_interactions = len(logs)
    
    # Latency stats
    latencies = [log.get("latency_ms", 0) for log in logs]
    retrieval_latencies = [log.get("retrieval_latency_ms", 0) for log in logs if log.get("retrieval_latency_ms")]
    generation_latencies = [log.get("generation_latency_ms", 0) for log in logs if log.get("generation_latency_ms")]
    
    # Token stats
    prompt_tokens = [log.get("prompt_tokens", 0) for log in logs if log.get("prompt_tokens")]
    completion_tokens = [log.get("completion_tokens", 0) for log in logs if log.get("completion_tokens")]
    
    # Error stats
    errors = [log for log in logs if log.get("error")]
    error_rate = len(errors) / total_interactions * 100 if total_interactions > 0 else 0
    
    # Retrieval stats
    retrievals_with_docs = [log for log in logs if log.get("num_retrieved", 0) > 0]
    retrieval_rate = len(retrievals_with_docs) / total_interactions * 100 if total_interactions > 0 else 0
    
    # Model usage
    models_used = {}
    for log in logs:
        model = log.get("model_name", "unknown")
        models_used[model] = models_used.get(model, 0) + 1
    
    # Time range
    timestamps = [log.get("timestamp") for log in logs if log.get("timestamp")]
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
            "total_interactions": total_interactions,
            "time_range": time_range,
            "error_rate_percent": round(error_rate, 2),
            "retrieval_rate_percent": round(retrieval_rate, 2)
        },
        "latency_stats": {
            "total_latency_ms": {
                "mean": round(statistics.mean(latencies), 2) if latencies else 0,
                "median": round(statistics.median(latencies), 2) if latencies else 0,
                "min": min(latencies) if latencies else 0,
                "max": max(latencies) if latencies else 0
            },
            "retrieval_latency_ms": {
                "mean": round(statistics.mean(retrieval_latencies), 2) if retrieval_latencies else 0,
                "median": round(statistics.median(retrieval_latencies), 2) if retrieval_latencies else 0,
            } if retrieval_latencies else None,
            "generation_latency_ms": {
                "mean": round(statistics.mean(generation_latencies), 2) if generation_latencies else 0,
                "median": round(statistics.median(generation_latencies), 2) if generation_latencies else 0,
            } if generation_latencies else None
        },
        "token_stats": {
            "prompt_tokens": {
                "mean": round(statistics.mean(prompt_tokens), 2) if prompt_tokens else 0,
                "total": sum(prompt_tokens) if prompt_tokens else 0
            },
            "completion_tokens": {
                "mean": round(statistics.mean(completion_tokens), 2) if completion_tokens else 0,
                "total": sum(completion_tokens) if completion_tokens else 0
            }
        },
        "models_used": models_used,
        "errors": {
            "count": len(errors),
            "examples": [{"timestamp": e.get("timestamp"), "error": e.get("error"), "query": e.get("user_query", "")[:50]} for e in errors[:5]]
        }
    }
    
    return analysis


def print_analysis(analysis: Dict[str, Any]):
    """Print the analysis in a readable format."""
    print("=" * 60)
    print("RAG SYSTEM LOG ANALYSIS")
    print("=" * 60)
    
    if "error" in analysis:
        print(f"Error: {analysis['error']}")
        return
    
    # Summary
    summary = analysis["summary"]
    print(f"\n📊 SUMMARY")
    print(f"   Total Interactions: {summary['total_interactions']}")
    print(f"   Time Range: {summary['time_range']}")
    print(f"   Error Rate: {summary['error_rate_percent']}%")
    print(f"   Retrieval Rate: {summary['retrieval_rate_percent']}%")
    
    # Latency stats
    latency = analysis["latency_stats"]
    print(f"\n⏱️  LATENCY STATISTICS")
    print(f"   Total Latency: {latency['total_latency_ms']['mean']}ms avg, {latency['total_latency_ms']['median']}ms median")
    print(f"                  {latency['total_latency_ms']['min']}-{latency['total_latency_ms']['max']}ms range")
    
    if latency.get("retrieval_latency_ms"):
        ret_lat = latency["retrieval_latency_ms"]
        print(f"   Retrieval: {ret_lat['mean']}ms avg, {ret_lat['median']}ms median")
    
    if latency.get("generation_latency_ms"):
        gen_lat = latency["generation_latency_ms"]
        print(f"   Generation: {gen_lat['mean']}ms avg, {gen_lat['median']}ms median")
    
    # Token stats
    tokens = analysis["token_stats"]
    print(f"\n🔤 TOKEN USAGE")
    print(f"   Prompt Tokens: {tokens['prompt_tokens']['total']} total, {tokens['prompt_tokens']['mean']} avg")
    print(f"   Completion Tokens: {tokens['completion_tokens']['total']} total, {tokens['completion_tokens']['mean']} avg")
    
    # Models
    print(f"\n🤖 MODELS USED")
    for model, count in analysis["models_used"].items():
        print(f"   {model}: {count} interactions")
    
    # Errors
    errors = analysis["errors"]
    if errors["count"] > 0:
        print(f"\n❌ ERRORS ({errors['count']} total)")
        for i, error in enumerate(errors["examples"], 1):
            print(f"   {i}. {error['timestamp']}: {error['error']}")
            print(f"      Query: {error['query']}...")
    else:
        print(f"\n✅ NO ERRORS FOUND")


def main():
    parser = argparse.ArgumentParser(description="Analyze RAG interaction logs")
    parser.add_argument(
        "--log-file", 
        default="logs/rag_interactions.jsonl",
        help="Path to the JSONL log file (default: logs/rag_interactions.jsonl)"
    )
    parser.add_argument(
        "--output",
        choices=["console", "json"],
        default="console",
        help="Output format (default: console)"
    )
    
    args = parser.parse_args()
    
    # Load logs
    logs = load_jsonl_logs(args.log_file)
    
    if not logs:
        print("No logs found or file doesn't exist yet.")
        return
    
    # Analyze logs
    analysis = analyze_logs(logs)
    
    # Output results
    if args.output == "json":
        print(json.dumps(analysis, indent=2))
    else:
        print_analysis(analysis)


if __name__ == "__main__":
    main()
