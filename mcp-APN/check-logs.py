import boto3
from datetime import datetime, timedelta

session = boto3.Session(profile_name="dati-quick-labs", region_name="us-east-1")
logs = session.client("logs")

# Listar streams mais recentes
streams = logs.describe_log_streams(
    logGroupName="/aws/lambda/partner-central-mcp-proxy",
    orderBy="LastEventTime",
    descending=True,
    limit=5,
)

print(f"Total streams: {len(streams['logStreams'])}")
for stream in streams["logStreams"]:
    name = stream["logStreamName"]
    last = datetime.fromtimestamp(stream.get("lastEventTimestamp", 0) / 1000)
    print(f"\n{'='*80}")
    print(f"Stream: {name}")
    print(f"Last event: {last}")
    print(f"{'='*80}")
    events = logs.get_log_events(
        logGroupName="/aws/lambda/partner-central-mcp-proxy",
        logStreamName=name,
        startFromHead=False,
        limit=50,
    )
    for event in events["events"]:
        msg = event["message"].strip()
        ts = datetime.fromtimestamp(event["timestamp"] / 1000)
        if msg:
            print(f"[{ts.strftime('%H:%M:%S')}] {msg}")
