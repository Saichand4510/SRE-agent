# Database Connection Timeout

## Symptoms
- High API latency
- Database timeout errors
- Connection pool exhaustion

## Root Cause
Usually caused by database overload or insufficient connection pool size.

## Resolution
- Increase DB connection pool size
- Restart the affected service
- Check database CPU usage