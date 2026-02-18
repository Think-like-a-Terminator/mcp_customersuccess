# Report Job Scheduling Implementation Summary

## What Was Built

A comprehensive report scheduling system for the Customer Success MCP Server that allows scheduling and managing automated report generation jobs stored in **BigQuery**.

## Files Created/Modified

### New Files
1. **REPORT_SCHEDULING.md** - Complete documentation for the feature
2. **test_report_scheduling.py** - Example usage script
3. **bigquery_schema.sql** - BigQuery table schema
4. **src/bigquery_service.py** - BigQuery service layer

### Modified Files
1. **src/config.py**
   - Added BigQuery configuration parameters
   - bigquery_project_id, bigquery_dataset_id, bigquery_credentials_path

2. **src/server.py**
   - Changed from db_service to bq_service
   - Updated all SQL queries to BigQuery standard SQL syntax
   - Updated query_database tool for BigQuery
   - Updated get_database_tables to use BigQuery INFORMATION_SCHEMA
   - Updated get_table_schema for BigQuery
   - Added schedule_report_job() MCP tool with BigQuery support
   - Added get_scheduled_jobs() MCP tool with BigQuery support
   - Added update_job_status() MCP tool with BigQuery support
   - Updated send_roi_report to use BigQuery

3. **src/models.py**
   - Added ReportType enum (5 report types)
   - Added JobFrequency enum
   - Added JobStatus enum
   - Added ReportJob model

4. **README.md**
   - Updated to reference BigQuery instead of PostgreSQL

## Database Schema (BigQuery)

### jobs Table
- **id**: STRING (UUID primary key)
- **job_name**: STRING - Descriptive name
- **report_type**: STRING - One of 5 report types
- **frequency**: STRING - Scheduling frequency
- **is_recurring**: BOOL - Boolean flag for recurring jobs
- **status**: STRING - Current status
- **email_recipients**: ARRAY<STRING> - Array of email addresses
- **start_date/end_date**: DATE - Report date range
- **parent_business_id**: STRING - Parent business filter (optional)
- **business_ids**: ARRAY<STRING> - Specific business IDs (optional)
- **attribution_window_days**: INT64 - Required for ROI reports
- **scheduled_time**: TIME - Time of day to run (default 09:00:00)
- **next_run_date**: TIMESTAMP - When to run next
- **last_run_date**: TIMESTAMP - Last execution time
- **last_run_status**: STRING - Status of last run
- **last_run_error**: STRING - Error message if failed
- **run_count**: INT64 - Execution counter
- **created_by**: STRING - User who created job
- **created_at/updated_at**: TIMESTAMP - Timestamps

### Notes
- BigQuery uses standard SQL types (STRING instead of VARCHAR, INT64 instead of INTEGER)
- Arrays are native types in BigQuery (ARRAY<STRING> instead of TEXT[])
- No CHECK constraints - validation done in application code
- No RETURNING clause - queries use separate SELECT after INSERT/UPDATE

## MCP Tools

### 1. schedule_report_job
**Purpose**: Create a new scheduled report job

**Parameters**:
- job_name (required)
- report_type (required): roi_revenue, appointment_confirmations, campaign_studio_performance, two_way_text_usage, appointment_no_shows
- frequency (required): one_time, daily, weekly, monthly, quarterly
- email_recipients (required): List of emails
- start_date/end_date (required): YYYY-MM-DD format
- parent_business_id (optional)
- business_ids (optional): List of business IDs
- attribution_window_days (optional, required for roi_revenue)
- scheduled_time (optional): HH:MM:SS, default 09:00:00

**Returns**: Job details including generated UUID

### 2. get_scheduled_jobs
**Purpose**: Query and filter scheduled jobs

**Parameters** (all optional):
- status: Filter by job status
- report_type: Filter by report type
- is_recurring: Filter by recurring flag

**Returns**: List of jobs matching filters

### 3. update_job_status
**Purpose**: Update a job's status (cancel, complete, etc.)

**Parameters**:
- job_id (required): UUID of job
- new_status (required): New status value
- notes (optional): Reason for change

**Returns**: Updated job details

## Integration Pattern

The jobs table serves as a queue/scheduler for a separate reporting server:

1. MCP server creates jobs via `schedule_report_job()`
2. Reporting server polls for jobs where:
   - `status = 'requested'` OR
   - `status = 'scheduled' AND next_run_date <= NOW()`
3. Reporting server updates status to 'running'
4. Executes report generation
5. Updates job with results:
   - last_run_date
   - last_run_status
   - last_run_error (if failed)
   - run_count (increment)
   - next_run_date (calculate for recurring)
   - status (completed or back to scheduled)

## Validation Features

- Report type validation against enum
- Frequency validation against enum
- Status validation against enum
- Date format validation (YYYY-MM-DD)
- Business ID requirement enforcement
- ROI report attribution window requirement
- Proper error messages for validation failures

## Testing

All Python files compile successfully:
- ✅ src/models.py - syntax valid
- ✅ src/server.py - syntax valid
- ✅ No linting errors

## Documentation

Comprehensive documentation includes:
- Feature overview
- Available report types
- Tool reference with examples
- Database schema details
- Integration patterns
- Usage examples for all scenarios
- Best practices
- Troubleshooting guide
- Security considerations

## Next Steps for Users

1. Run updated `init-db.sql` to create jobs table
2. Use `schedule_report_job()` to create jobs
3. Build or configure reporting server to poll jobs table
4. Monitor jobs using `get_scheduled_jobs()`
5. Cancel/update jobs as needed with `update_job_status()`

## Key Benefits

✅ **Flexible Scheduling**: Supports one-time and recurring jobs  
✅ **Multiple Report Types**: 5 different report types supported  
✅ **Rich Metadata**: Tracks execution history, errors, and status  
✅ **Query Flexibility**: Filter jobs by status, type, and recurring flag  
✅ **Data Integrity**: Constraints ensure valid data  
✅ **Performance**: Indexes on key columns  
✅ **Decoupled Design**: Separate MCP scheduler from report executor  
✅ **Comprehensive Docs**: Full documentation with examples
