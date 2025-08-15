# aws-cost-monitoring-tool
Tool that augments services in the AWS environment to report and detect data regarding cost and usage in AWS in the form of dashboards and alerts.

## Architecture Overview
![Image of Solution Architecture](./imgs/architecture.jpeg)

## Build
### 1. Create S3 Bucket to house Lambda code
First, create a Cloudformation Stack (new resources option) and upload the `lambda_code_bucket.yaml` template file. 

(fix steps below)

Once the Cloudformation Stack is created, compress each of `.py` files in `lambdas-py` folder to a `.zip` format with their respective names (`metric-data-creation.zip` & `automated-dashboard-creation`) and upload it to the bucket that was created by the Stack.

### 2. Remaining Architecture
Second, deploy the `cef_tool_infrastucture3.yaml` template file through another Cloudformation Stack (new resources option).
#### Important Note in regards to YAML default:
- Glue Crawler frequency is set to On Demand.
- EventBridge Scheduler is Disabled.

### 3. Setting up CUR Reports forwarding to S3
In AWS, go to Billing and Cost Management --> Data Exports --> Create:

![Image of Data Exports Screen](./imgs/data_exports.png)

#### Once `Create` is pressed, adhere to these settings for the report:
- Data table content settings --> CUR 2.0
- (ignore additional export content unless wanted)
- Time granularity --> Daily
- Compression type and file format --> Parquet - Parquet
- File versioning --> Overwrite existing data export file
- S3 Bucket --> Select existing bucket --> Select the bucket under the naming convention `aws-daily-cur-reports-${AWS::AccountId}-${AWS::Region}`

