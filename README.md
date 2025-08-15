# aws-cost-monitoring-tool
Tool that augments services in the AWS environment to report and detect data regarding cost and usage in AWS in the form of dashboards and alerts.

## Architecture Overview
(img here)

### Create S3 Bucket to house Lambda code
First, create a Cloudformation Stack (new resources option) and upload the `lambda_code_bucket.yaml` template file. 

Once the Cloudformation Stack is created, head to S3 and either upload `automated-dashboard-creation.zip` and `metric-data-creation.zip` from this repo OR compress each of `.py` files in `lambdas-py` to a `.zip` format with their respective names


