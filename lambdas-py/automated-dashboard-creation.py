import json
import boto3
import time
from datetime import datetime,timezone,timedelta

cloudwatch = boto3.client("cloudwatch")
length_list = []

def create_dashboard_definiton(width,height,view,title,x=0,y=0,ad='n',lst=None,string="",sparkline_status=False,period=3600,color=None): 
    tmp_metric_name,tmp_dimension_name,tmp_dimension_value = lst
    dashboard_definition = {
        "widgets":[
            {
                "type": "metric",
                "x":x,
                "y":y,
                "width":width,
                "height":height,
                "properties":{
                    "metrics": [
                        [ "Cost Metrics", tmp_metric_name, tmp_dimension_name, tmp_dimension_value]
                    ],
                    "view":view,
                    "period":period,
                    "stat":"Average",
                    "region":"us-east-1",
                    "title": title+string,
                    "stacked":False,
                    "sparkline":sparkline_status
                }
            }
        ]
    }
    
    if ad == 'y':
        expression = [ { "expression": "ANOMALY_DETECTION_BAND(m1, 2)", "label": "unblended_total (expected)", "id": "ad1", "color": "#95A5A6", "period": 900 }]
        dashboard_definition["widgets"][0]["properties"]["metrics"].append(expression)
        dashboard_definition["widgets"][0]["properties"]["metrics"][0].append({ "id": "m1" })
    
    if view == "timeSeries":
        y_axis = {
            "left": {
                "label": "Cost (USD)",
                "showUnits": False
            }
        }
        dashboard_definition["widgets"][0]["properties"]["yAxis"] = y_axis

    if color != None:
        dashboard_definition["widgets"][0]["properties"]["metrics"][0].append({"color":color})


    return (dashboard_definition,view)


def create_dashboard(name,json_def):
    cloudwatch.put_dashboard(
        DashboardName=name,
        DashboardBody=json.dumps(json_def)
    )
#

def check_metric_value(test,start_time="",end_time="",period=60):
    current_vals = []
    sorted_highest_vals = []
    
    if start_time == "" and end_time == "":
        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(minutes=60)
        end_time = datetime.now(timezone.utc) + timedelta(minutes=3)
    for item in test:
        metric_statistic_response = cloudwatch.get_metric_statistics(
            Namespace=item["Namespace"],
            MetricName=item["MetricName"],
            Dimensions=[
                {"Name":item["Dimensions"][0]["Name"],"Value":item["Dimensions"][0]["Value"]}
            ],
            StartTime=start_time,
            EndTime=end_time,
            Period=period,
            Statistics=['Average']
        )

        if metric_statistic_response["Datapoints"] == []:
            continue
        elif len(test) > 1 and item["MetricName"] == "service-name-cost-usd":
            sorted_highest_vals.append([metric_statistic_response["Datapoints"][0]["Average"],item])
            sorted_highest_vals = sorted(x,key=lambda avg:avg[0])
            current_vals = [sorted_highest_vals[-1][1]]
        else:
            current_vals.append(item)

    return current_vals

def get_metrics(metric_name,dimension_name,namespace='Cost Metrics',s_d="",e_d="",p_d=60):
    metrics = cloudwatch.list_metrics(
            Namespace=namespace,
            MetricName=metric_name,
            Dimensions=[
                {
                    "Name": dimension_name
                }
            ]
        )
    
    #Modify before IaC
    if len(metrics["Metrics"]) == 2:
        length_list.append(len(metrics["Metrics"]))
        metric_dict = metrics["Metrics"][1]
        if '?' in list(metric_dict["Dimensions"][0].values()):
            metric_dict = metrics["Metrics"][0]
            yield [metric_dict["MetricName"]] + list(metric_dict["Dimensions"][0].values())
        else:
            yield [metric_dict["MetricName"]] + list(metric_dict["Dimensions"][0].values())
    else:
        metrics["Metrics"] = check_metric_value(metrics["Metrics"],start_time=s_d,end_time=e_d,period=p_d)
        length_list.append(len(metrics["Metrics"]))
        for element in range(len(metrics["Metrics"])):
            metric_dict = metrics["Metrics"][element]
            yield [metric_dict["MetricName"]] + list(metric_dict["Dimensions"][0].values())

def configure_widgets(date_start="",date_end="",pd=60):
    
    if date_start != "" and date_end != "":
        widgets = {"start":date_start,"end":date_end,"widgets":[]}
    else:
        widgets = {"widgets":[]}

    custom_metric_vals = [
        
        get_metrics("DailyUnblendedCost-USD","TotalDailyCost",s_d=date_start,e_d=date_end,p_d=pd),
        get_metrics("service-name-cost-usd","HighestDailyServiceCost",s_d=date_start,e_d=date_end,p_d=pd),
        get_metrics("num_services","Total # of Services Used",s_d=date_start,e_d=date_end,p_d=pd),
        get_metrics("t6_product_cost","Top 6 Services",s_d=date_start,e_d=date_end,p_d=pd),
        get_metrics("region_spend","Costs by Region",s_d=date_start,e_d=date_end,p_d=pd),
        get_metrics("total_account_cost","Total USD Spent Since Account Creation",s_d=date_start,e_d=date_end,p_d=pd)
        
    ]

    for custom_metric_vals_length_list in range(len(custom_metric_vals)):
        full_view_bar_list = []
        for i in custom_metric_vals[custom_metric_vals_length_list]:
            dashboard_jsons = [
                create_dashboard_definiton(24,7,"timeSeries","Total Daily Inccured Cost",ad='y',lst=i),
                create_dashboard_definiton(6,6,"singleValue","Highest Service Cost",ad='n',lst=i,string=" - " + i[-1],sparkline_status=True),
                create_dashboard_definiton(6,6,"singleValue","Number of Services Used (monthly)",ad='n',lst=i,x=6,y=0),
                create_dashboard_definiton(12,6,"bar","Top 6 Service Costs",ad='n',lst=i,x=17,y=10),
                create_dashboard_definiton(8,7,"pie","Cost per Region",ad='n',lst=i,y=10),
                create_dashboard_definiton(16,7,"timeSeries","Absolute Account Cost",ad='n',lst=i,x=17,y=20,color="#17becf")
            ]

            view_state = dashboard_jsons[custom_metric_vals_length_list][1]

            if view_state in ["pie","bar"] and len(full_view_bar_list) == length_list[-1]-1:
                widgets["widgets"].append(dashboard_jsons[custom_metric_vals_length_list][0]["widgets"][0])
                for _ in full_view_bar_list:
                    widgets["widgets"][-1]['properties']['metrics'].append(_)

            elif view_state in ["pie","bar"] and len(full_view_bar_list) < length_list[-1]:
                single_view_bar_list = ["...",i[-1],{"region":"us-east-1"}]
                full_view_bar_list.append(single_view_bar_list)
                continue

            else:
                widgets["widgets"].append(dashboard_jsons[custom_metric_vals_length_list][0]["widgets"][0])

    return widgets

def lambda_handler(event, context):
    
    current_month_dashboard = configure_widgets()
    previous_month_dashboard = configure_widgets(date_start="2025-07-25T00:00:00.000Z",date_end="2025-08-01T23:59:59.000Z",pd=3600)

    #note: CHANGE previous_month_dashboard to have it configure to correct previous month timeline
        
    create_dashboard("cloudwatch-cost-and-usage-dashboard",current_month_dashboard)
    create_dashboard("previous-month-cloudwatch-cost-and-usage-dashboard",previous_month_dashboard)

    return {
        'statusCode': 200,
        'body': str("Success!")
    }
