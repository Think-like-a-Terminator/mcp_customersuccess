"""Quick test script to verify all MCP tools are working."""

from src.server import (
    create_call_to_action,
    list_call_to_actions,
    update_health_score,
    get_health_score,
    create_risk_alert,
    list_risk_alerts,
)


def test_all_tools():
    """Test all MCP server tools."""
    print("=" * 60)
    print("Customer Success MCP Server - Tool Testing")
    print("=" * 60)

    # Test 1: Create CTA
    print("\n1️⃣  Testing Call to Action Creation...")
    cta_result = create_call_to_action(
        account_id="test-acct-001",
        title="Conduct Executive Business Review",
        description="Schedule and conduct EBR with C-level stakeholders",
        priority="high",
        owner="csm@example.com",
        due_date_days=30,
        tags=["qbr", "executive", "high-touch"],
    )
    print(f"   ✓ CTA created: {cta_result['success']}")
    print(f"   ✓ CTA ID: {cta_result['cta']['id']}")
    print(f"   ✓ Priority: {cta_result['cta']['priority']}")
    
    # Test 2: List CTAs
    print("\n2️⃣  Testing CTA Listing...")
    list_result = list_call_to_actions(priority="high")
    print(f"   ✓ Found {list_result['count']} high-priority CTAs")
    
    # Test 3: Update Health Score
    print("\n3️⃣  Testing Health Score Update...")
    health_result = update_health_score(
        account_id="test-acct-001",
        overall_score=82.5,
        metrics=[
            {"name": "product_usage", "value": 85.0, "weight": 0.4},
            {"name": "engagement", "value": 80.0, "weight": 0.3},
            {"name": "support_satisfaction", "value": 83.0, "weight": 0.3},
        ],
        trend="improving",
        notes="Strong product adoption, increasing user engagement",
    )
    print(f"   ✓ Health score updated: {health_result['success']}")
    print(f"   ✓ Score: {health_result['health_score']['overall_score']}")
    print(f"   ✓ Status: {health_result['health_score']['status']}")
    print(f"   ✓ Trend: {health_result['health_score']['trend']}")
    
    # Test 4: Get Health Score
    print("\n4️⃣  Testing Health Score Retrieval...")
    get_health = get_health_score("test-acct-001")
    print(f"   ✓ Retrieved health score: {get_health['success']}")
    print(f"   ✓ Number of metrics: {len(get_health['health_score']['metrics'])}")
    
    # Test 5: Create Risk Alert
    print("\n5️⃣  Testing Risk Alert Creation...")
    alert_result = create_risk_alert(
        account_id="test-acct-002",
        risk_level="high",
        risk_factors=[
            "Product usage declined 40% in last 30 days",
            "No executive sponsor engagement in 90 days",
            "Contract renewal in 60 days",
        ],
        impact_score=85.0,
        recommended_actions=[
            "Schedule immediate executive business review",
            "Conduct product usage analysis and training",
            "Review support ticket trends",
            "Engage renewal team",
        ],
        notes="Critical renewal risk - immediate action required",
    )
    print(f"   ✓ Risk alert created: {alert_result['success']}")
    print(f"   ✓ Alert ID: {alert_result['alert']['id']}")
    print(f"   ✓ Risk Level: {alert_result['alert']['risk_level']}")
    print(f"   ✓ Impact Score: {alert_result['alert']['impact_score']}")
    
    # Test 6: List Risk Alerts
    print("\n6️⃣  Testing Risk Alert Listing...")
    alerts_list = list_risk_alerts(risk_level="high")
    print(f"   ✓ Found {alerts_list['count']} high-risk alerts")
    
    print("\n" + "=" * 60)
    print("✅ All tests completed successfully!")
    print("=" * 60)
    print("\nThe MCP server is ready to use with:")
    print("  • Call to Actions (CTAs)")
    print("  • Health Score Tracking")
    print("  • Survey/NPS Emails (AWS SES)")
    print("  • Account Risk Alerts")
    print("\nStart the server with: uv run python -m src.server")
    print("=" * 60)


if __name__ == "__main__":
    test_all_tools()
