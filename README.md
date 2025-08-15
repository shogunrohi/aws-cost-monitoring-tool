# aws-cost-monitoring-tool
Tool that augments services in the AWS environment to report and detect data regarding cost and usage in AWS in the form of dashboards and alerts.

## Architecture Overview
(img here)

### Create S3 Bucket to house Lambda code
First, create a Cloudformation Stack (new resources option) and upload the `lambda_code_bucket.yaml` template file. 

Once the Cloudformation Stack is created, compress each of `.py` files in `lambdas-py` folder to a `.zip` format with their respective names (`metric-data-creation.zip` & `automated-dashboard-creation`) and upload it to the bucket that was created by the Stack.


