import boto3
import time
from datetime import datetime, timezone, timedelta
import csv
import io
import pandas as pd

athena = boto3.client("athena")
cloudwatch = boto3.client("cloudwatch")
s3 = boto3.client("s3")

def query_results(query_string,query_database,output_location):

    start_query = athena.start_query_execution(
        QueryString=query_string,
        QueryExecutionContext={'Database':query_database},
        ResultConfiguration={"OutputLocation":output_location}
        )

    query_execution_id = start_query["QueryExecutionId"]

    while True:
        response = athena.get_query_execution(QueryExecutionId=query_execution_id)
        status = response['QueryExecution']['Status']['State']

        if status == "SUCCEEDED":
            break
        elif status in ["FAILED","CANCELED"]:
            print(f"Query: {status}")
            err = (response["QueryExecution"]['Status'].get("StateChangeReason"))
            return err
        else:
            print(f"Query {status}")
            time.sleep(10)

    results = athena.get_query_results(QueryExecutionId=query_execution_id)
    return results

def zip_results(lst):
    lst = lst[1:]
    tmp,tmp2 = [],[]
    for item in lst:
        for item2 in item["Data"]:
            if item2 == {}:
                tmp.append('global')
            else:
                tmp.append(item2['VarCharValue'])
        tmp2.append(tuple(tmp))
        tmp.clear()
    return tmp2

def create_alarm(m_d,alarm_name,description="",namespace="Cost Metrics"):
    alarm_response = cloudwatch.put_metric_alarm(
        AlarmName=alarm_name,
        EvaluationPeriods=1,
        DatapointsToAlarm=1,
        ComparisonOperator="LessThanLowerOrGreaterThanUpperThreshold",
        ThresholdMetricId='ad1',
        TreatMissingData="missing",
        Metrics=[
            {
                'Id':'m1',
                'MetricStat':{
                    "Metric":{
                        'Namespace':namespace,
                        'MetricName':m_d["MetricName"],
                        'Dimensions':m_d["Dimensions"]
                    },
                    'Period':3600,
                    'Stat':'Average'
                },
            },
            {
                'Id':'ad1',
                'Expression':'ANOMALY_DETECTION_BAND(m1,2)',
                'Label':f"{m_d["MetricName"]} (expected)",
                'ReturnData': True
            }
        ],
        AlarmDescription= "Alarm created to check if the total daily (unblended) cost exceeds or falls below the set threshold.",
        ActionsEnabled=True
    )

def push_metric(value,metric_name,dimension_name=None,dimension_value=None,anomaly_detection='n',alarm='n',desc="",a_n="",current_time=datetime.now().isoformat()):
    metric_data_dict = {
        'MetricName': metric_name,
        'Value': float(value),
        'Unit': 'None',
        'Timestamp': current_time
    }
    if dimension_name != None and dimension_value != None:
        metric_data_dict["Dimensions"] = [
            {
                "Name":dimension_name,
                "Value":dimension_value
            }
        ]

    cloudwatch.put_metric_data(
        Namespace='Cost Metrics',
        MetricData=[metric_data_dict]
    )

    if anomaly_detection == 'y':
        cloudwatch.put_anomaly_detector(
            Namespace='Cost Metrics',
            MetricName= metric_data_dict['MetricName'],
            Dimensions=metric_data_dict["Dimensions"],
            Stat="Average"
        )
    if alarm == 'y':
        create_alarm(metric_data_dict,a_n,description=desc)


def lambda_handler(event, context):
    database = "hourly-cur-database"
    s3_output = "s3://dashbaord-athena-query-results/"
    catalog_name = 'AwsDataCatalog'

    table_name = athena.list_table_metadata(CatalogName=catalog_name, DatabaseName=database)['TableMetadataList'][0]['Name']

    time_now = datetime.now()
    billing_period = time_now.strftime("%Y-%m")
    prev_billing_period =(pd.to_datetime(time_now) - pd.DateOffset(months=1)).strftime("%Y-%m")

    queries = {
        "total_daily_cost_query":f'SELECT ABS(SUM("line_item_unblended_cost")) AS service_cost FROM "{database}"."{table_name}" WHERE billing_period = \'{billing_period}\' AND "line_item_line_item_type" = \'Credit\';',
        
        "highest_daily_service_cost_query":f'SELECT "line_item_product_code", ABS(SUM("line_item_unblended_cost")) AS service_cost FROM "{database}"."{table_name}" WHERE billing_period = \'{billing_period}\' AND "line_item_line_item_type" = \'Credit\' GROUP BY "line_item_product_code" ORDER BY service_cost DESC LIMIT 1',
        
        "total_used_services_query":f'SELECT COUNT(DISTINCT "line_item_product_code") FROM "{database}"."{table_name}" WHERE billing_period = \'{billing_period}\'',
        
        "consumed_region_spend_query":f'SELECT "product_region_code", ABS(SUM("line_item_unblended_cost")) AS total_unblended_cost FROM "{database}"."{table_name}" WHERE billing_period = \'{billing_period}\' AND "line_item_line_item_type" = \'Credit\' GROUP BY "product_region_code" ORDER BY total_unblended_cost DESC;',
        
        "overall_account_cost_query":f'SELECT SUM(service_cost) AS total_service_cost FROM (SELECT ABS(SUM("line_item_unblended_cost")) AS service_cost FROM "{database}"."{table_name}" WHERE billing_period = \'{billing_period}\' AND "line_item_line_item_type" = \'Credit\' UNION ALL SELECT SUM("line_item_unblended_cost") AS service_cost FROM "{database}"."{table_name}" WHERE billing_period = \'{prev_billing_period}\') AS combined_costs;'
        # "overall_account_cost" query will have to be modified, this is just a temporary solution as there's an issue will the billing w/line_item_line_item_type.
    }
    
    queries["top_6_cost_services_query"] = queries["highest_daily_service_cost_query"][:-1] + "6"
    
    used_total_services = zip_results(query_results(queries["total_used_services_query"],database,s3_output)["ResultSet"]["Rows"])
    
    uts_response = push_metric(
        used_total_services[0][0],
        "num_services",
        dimension_name="Total # of Services Used",
        dimension_value="amount_services_consumed",
    )

    total_cost_daily = zip_results(query_results(queries["total_daily_cost_query"],database,s3_output)["ResultSet"]["Rows"])
    
    tcd_response = push_metric(
        total_cost_daily[0][0],
        "DailyUnblendedCost-USD",
        dimension_name="TotalDailyCost",
        dimension_value="unblended_total",
        anomaly_detection='y',
        alarm='y',
        desc="Alarm created to check if the total daily (unblended) cost exceeds or falls below the set threshold.",
        a_n="check-daily-cost-alarm"
    )

    total_account_cost = zip_results(query_results(queries["overall_account_cost_query"],database,s3_output)["ResultSet"]["Rows"])
    
    tac_response = push_metric(
        total_account_cost[0][0],
        "total_account_cost",
        dimension_name="Total USD Spent Since Account Creation",
        dimension_value="all_account_cost",
    )
    
    highest_daily_service_cost = zip_results(query_results(queries["highest_daily_service_cost_query"],database,s3_output)["ResultSet"]["Rows"])
    highest_cost_service, service_specfic_cost = highest_daily_service_cost[0][0],highest_daily_service_cost[0][1]

    hdsc_response = push_metric(service_specfic_cost,"service-name-cost-usd",dimension_name="HighestDailyServiceCost",dimension_value=highest_cost_service)
    
    top_6_today = zip_results(query_results(queries["top_6_cost_services_query"],database,s3_output)["ResultSet"]["Rows"])

    for t6_pair in top_6_today:
        product, charge = t6_pair
        t6_response = push_metric(charge,"t6_product_cost",dimension_name="Top 6 Services",dimension_value=product)
    
    region_spend = zip_results(query_results(queries["consumed_region_spend_query"],database,s3_output)["ResultSet"]["Rows"])
    
    for region_pair in region_spend:
        product, charge = region_pair
        rs_response = push_metric(charge,"region_spend",dimension_name="Costs by Region",dimension_value=product)
    
    return {
        'statusCode': 200,
        'body': "Success!"
    }
