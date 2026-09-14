# ChicagoPulse Genie Benchmark Suite

## 1. Which 10 Community Areas had the most 311 requests in the last completed month?

Category: Basic metrics

```sql
WITH latest AS (SELECT MAX(metric_month) AS metric_month FROM workspace.chicagopulse.mv_neighborhood_pulse)
SELECT community_area_name,
       MEASURE(total_311_requests) AS total_311_requests
FROM workspace.chicagopulse.mv_neighborhood_pulse
WHERE metric_month = (SELECT metric_month FROM latest)
  AND community_area_name IS NOT NULL
GROUP BY community_area_name
ORDER BY total_311_requests DESC
LIMIT 10
```

## 2. How many 311 requests were recorded across Chicago in the last completed month?

Category: Basic metrics

```sql
WITH latest AS (SELECT MAX(metric_month) AS metric_month FROM workspace.chicagopulse.mv_neighborhood_pulse)
SELECT MEASURE(total_311_requests) AS total_311_requests
FROM workspace.chicagopulse.mv_neighborhood_pulse
WHERE metric_month = (SELECT metric_month FROM latest)
```

## 3. Which 10 Community Areas had the most building violations in the last completed month?

Category: Basic metrics

```sql
WITH latest AS (SELECT MAX(metric_month) AS metric_month FROM workspace.chicagopulse.mv_neighborhood_pulse)
SELECT community_area_name,
       MEASURE(total_building_violations) AS total_building_violations
FROM workspace.chicagopulse.mv_neighborhood_pulse
WHERE metric_month = (SELECT metric_month FROM latest)
  AND community_area_name IS NOT NULL
GROUP BY community_area_name
ORDER BY total_building_violations DESC
LIMIT 10
```

## 4. Which 10 Community Areas had the most building permits in the last completed month?

Category: Basic metrics

```sql
WITH latest AS (SELECT MAX(metric_month) AS metric_month FROM workspace.chicagopulse.mv_neighborhood_pulse)
SELECT community_area_name,
       MEASURE(total_building_permits) AS total_building_permits
FROM workspace.chicagopulse.mv_neighborhood_pulse
WHERE metric_month = (SELECT metric_month FROM latest)
  AND community_area_name IS NOT NULL
GROUP BY community_area_name
ORDER BY total_building_permits DESC
LIMIT 10
```

## 5. Which 10 Community Areas had the most business license issues in the last completed month?

Category: Basic metrics

```sql
WITH latest AS (SELECT MAX(metric_month) AS metric_month FROM workspace.chicagopulse.mv_neighborhood_pulse)
SELECT community_area_name,
       MEASURE(total_business_license_issues) AS total_business_license_issues
FROM workspace.chicagopulse.mv_neighborhood_pulse
WHERE metric_month = (SELECT metric_month FROM latest)
  AND community_area_name IS NOT NULL
GROUP BY community_area_name
HAVING MEASURE(total_business_license_issues) IS NOT NULL
ORDER BY total_business_license_issues DESC
LIMIT 10
```

## 6. Which 10 Community Areas had the most open 311 requests in the last completed month?

Category: Neighborhood comparisons

```sql
WITH latest AS (SELECT MAX(metric_month) AS metric_month FROM workspace.chicagopulse.mv_neighborhood_pulse)
SELECT community_area_name,
       MEASURE(open_311_requests) AS open_311_requests
FROM workspace.chicagopulse.mv_neighborhood_pulse
WHERE metric_month = (SELECT metric_month FROM latest)
  AND community_area_name IS NOT NULL
GROUP BY community_area_name
ORDER BY open_311_requests DESC
LIMIT 10
```

## 7. Which 10 Community Areas had the most open building violations in the last completed month?

Category: Neighborhood comparisons

```sql
WITH latest AS (SELECT MAX(metric_month) AS metric_month FROM workspace.chicagopulse.mv_neighborhood_pulse)
SELECT community_area_name,
       MEASURE(open_building_violations) AS open_building_violations
FROM workspace.chicagopulse.mv_neighborhood_pulse
WHERE metric_month = (SELECT metric_month FROM latest)
  AND community_area_name IS NOT NULL
GROUP BY community_area_name
ORDER BY open_building_violations DESC
LIMIT 10
```

## 8. Compare 311 requests, building violations, building permits, and business license issues for Austin, Lake View, West Town, and Lincoln Park in the last completed month.

Category: Neighborhood comparisons

```sql
WITH latest AS (SELECT MAX(metric_month) AS metric_month FROM workspace.chicagopulse.mv_neighborhood_pulse)
SELECT community_area_name,
       MEASURE(total_311_requests) AS total_311_requests,
       MEASURE(total_building_violations) AS total_building_violations,
       MEASURE(total_building_permits) AS total_building_permits,
       MEASURE(total_business_license_issues) AS total_business_license_issues
FROM workspace.chicagopulse.mv_neighborhood_pulse
WHERE metric_month = (SELECT metric_month FROM latest)
  AND community_area_name IN ('Austin','Lake View','West Town','Lincoln Park')
GROUP BY community_area_name
ORDER BY community_area_name
```

## 9. Which 10 Community Areas had the highest building permit fees in the last completed month?

Category: Neighborhood comparisons

```sql
WITH latest AS (SELECT MAX(metric_month) AS metric_month FROM workspace.chicagopulse.mv_neighborhood_pulse)
SELECT community_area_name,
       MEASURE(total_permit_fees) AS total_permit_fees
FROM workspace.chicagopulse.mv_neighborhood_pulse
WHERE metric_month = (SELECT metric_month FROM latest)
  AND community_area_name IS NOT NULL
GROUP BY community_area_name
HAVING MEASURE(total_permit_fees) IS NOT NULL
ORDER BY total_permit_fees DESC
LIMIT 10
```

## 10. Which 10 Community Areas had the most new construction permits in the last completed month?

Category: Neighborhood comparisons

```sql
WITH latest AS (SELECT MAX(metric_month) AS metric_month FROM workspace.chicagopulse.mv_neighborhood_pulse)
SELECT community_area_name,
       MEASURE(new_construction_permits) AS new_construction_permits
FROM workspace.chicagopulse.mv_neighborhood_pulse
WHERE metric_month = (SELECT metric_month FROM latest)
  AND community_area_name IS NOT NULL
GROUP BY community_area_name
HAVING MEASURE(new_construction_permits) IS NOT NULL
ORDER BY new_construction_permits DESC
LIMIT 10
```

## 11. What were the 15 most common 311 service request types across Chicago in the last completed month?

Category: 311 drilldowns

```sql
WITH latest AS (SELECT MAX(metric_month) AS metric_month FROM workspace.chicagopulse.mv_311_service_trends)
SELECT service_request_type,
       MEASURE(total_311_requests) AS total_311_requests
FROM workspace.chicagopulse.mv_311_service_trends
WHERE metric_month = (SELECT metric_month FROM latest)
GROUP BY service_request_type
ORDER BY total_311_requests DESC
LIMIT 15
```

## 12. What were the 10 most common 311 service request types in Near West Side in the last completed month?

Category: 311 drilldowns

```sql
WITH latest AS (SELECT MAX(metric_month) AS metric_month FROM workspace.chicagopulse.mv_311_service_trends)
SELECT service_request_type,
       MEASURE(total_311_requests) AS total_311_requests
FROM workspace.chicagopulse.mv_311_service_trends
WHERE metric_month = (SELECT metric_month FROM latest)
  AND community_area_name = 'Near West Side'
GROUP BY service_request_type
ORDER BY total_311_requests DESC
LIMIT 10
```

## 13. What were the 10 most common 311 service request types in O'Hare in the last completed month?

Category: 311 drilldowns

```sql
WITH latest AS (SELECT MAX(metric_month) AS metric_month FROM workspace.chicagopulse.mv_311_service_trends)
SELECT service_request_type,
       MEASURE(total_311_requests) AS total_311_requests
FROM workspace.chicagopulse.mv_311_service_trends
WHERE metric_month = (SELECT metric_month FROM latest)
  AND community_area_name = 'O''Hare'
GROUP BY service_request_type
ORDER BY total_311_requests DESC
LIMIT 10
```

## 14. Which 10 Community Areas had the longest average 311 resolution time in the last completed month, considering only areas with at least 100 resolved requests?

Category: 311 drilldowns

```sql
WITH latest AS (SELECT MAX(metric_month) AS metric_month FROM workspace.chicagopulse.mv_311_service_trends)
SELECT community_area_name,
       MEASURE(resolved_311_requests) AS resolved_311_requests,
       MEASURE(average_resolution_days) AS average_resolution_days
FROM workspace.chicagopulse.mv_311_service_trends
WHERE metric_month = (SELECT metric_month FROM latest)
GROUP BY community_area_name
HAVING MEASURE(resolved_311_requests) >= 100
ORDER BY average_resolution_days DESC
LIMIT 10
```

## 15. Which 15 service request types had the longest average resolution time in the last completed month, considering only types with at least 100 resolved requests?

Category: 311 drilldowns

```sql
WITH latest AS (SELECT MAX(metric_month) AS metric_month FROM workspace.chicagopulse.mv_311_service_trends)
SELECT service_request_type,
       MEASURE(resolved_311_requests) AS resolved_311_requests,
       MEASURE(average_resolution_days) AS average_resolution_days
FROM workspace.chicagopulse.mv_311_service_trends
WHERE metric_month = (SELECT metric_month FROM latest)
GROUP BY service_request_type
HAVING MEASURE(resolved_311_requests) >= 100
ORDER BY average_resolution_days DESC
LIMIT 15
```

## 16. Which 10 Community Areas had the largest month-over-month increase in 311 requests in the latest completed month, considering areas with at least 500 requests in the prior month?

Category: Time trends

```sql
WITH monthly AS (
  SELECT metric_month, community_area_name,
         MEASURE(current_month_311_requests) AS current_value,
         MEASURE(previous_month_311_requests) AS previous_value,
         MEASURE(request_mom_change_pct) AS change_pct
  FROM workspace.chicagopulse.mv_neighborhood_pulse
  GROUP BY metric_month, community_area_name
),
latest AS (SELECT MAX(metric_month) AS metric_month FROM monthly)
SELECT community_area_name,
       current_value,
       previous_value,
       change_pct
FROM monthly
WHERE metric_month = (SELECT metric_month FROM latest)
  AND previous_value >= 500
  AND change_pct IS NOT NULL
ORDER BY change_pct DESC
LIMIT 10
```

## 17. Which 10 Community Areas had the largest month-over-month decrease in 311 requests in the latest completed month, considering areas with at least 500 requests in the prior month?

Category: Time trends

```sql
WITH monthly AS (
  SELECT metric_month, community_area_name,
         MEASURE(current_month_311_requests) AS current_value,
         MEASURE(previous_month_311_requests) AS previous_value,
         MEASURE(request_mom_change_pct) AS change_pct
  FROM workspace.chicagopulse.mv_neighborhood_pulse
  GROUP BY metric_month, community_area_name
),
latest AS (SELECT MAX(metric_month) AS metric_month FROM monthly)
SELECT community_area_name,
       current_value,
       previous_value,
       change_pct
FROM monthly
WHERE metric_month = (SELECT metric_month FROM latest)
  AND previous_value >= 500
  AND change_pct IS NOT NULL
ORDER BY change_pct ASC
LIMIT 10
```

## 18. Which 10 Community Areas had the largest month-over-month increase in building violations in the latest completed month, considering areas with at least 50 violations in the prior month?

Category: Time trends

```sql
WITH monthly AS (
  SELECT metric_month, community_area_name,
         MEASURE(current_month_violations) AS current_value,
         MEASURE(previous_month_violations) AS previous_value,
         MEASURE(violation_mom_change_pct) AS change_pct
  FROM workspace.chicagopulse.mv_neighborhood_pulse
  GROUP BY metric_month, community_area_name
),
latest AS (SELECT MAX(metric_month) AS metric_month FROM monthly)
SELECT community_area_name,
       current_value,
       previous_value,
       change_pct
FROM monthly
WHERE metric_month = (SELECT metric_month FROM latest)
  AND previous_value >= 50
  AND change_pct IS NOT NULL
ORDER BY change_pct DESC
LIMIT 10
```

## 19. Show Austin's monthly 311 request volume for the latest 12 completed months.

Category: Time trends

```sql
WITH latest AS (SELECT MAX(metric_month) AS metric_month FROM workspace.chicagopulse.mv_neighborhood_pulse)
SELECT metric_month,
       MEASURE(total_311_requests) AS total_311_requests
FROM workspace.chicagopulse.mv_neighborhood_pulse
WHERE community_area_name = 'Austin'
  AND metric_month BETWEEN ADD_MONTHS((SELECT metric_month FROM latest),-11)
                       AND (SELECT metric_month FROM latest)
GROUP BY metric_month
ORDER BY metric_month
```

## 20. Show Chicago's total monthly 311 request volume for the latest 12 completed months.

Category: Time trends

```sql
WITH latest AS (SELECT MAX(metric_month) AS metric_month FROM workspace.chicagopulse.mv_neighborhood_pulse)
SELECT metric_month,
       MEASURE(total_311_requests) AS total_311_requests
FROM workspace.chicagopulse.mv_neighborhood_pulse
WHERE metric_month BETWEEN ADD_MONTHS((SELECT metric_month FROM latest),-11)
                       AND (SELECT metric_month FROM latest)
GROUP BY metric_month
ORDER BY metric_month
```

## 21. Which Community Areas had at least 3,000 311 requests and at least 100 building violations in the last completed month?

Category: Cross-dataset reasoning

```sql
WITH latest AS (SELECT MAX(metric_month) AS metric_month FROM workspace.chicagopulse.mv_neighborhood_pulse)
SELECT community_area_name,
       MEASURE(total_311_requests) AS total_311_requests,
       MEASURE(total_building_violations) AS total_building_violations
FROM workspace.chicagopulse.mv_neighborhood_pulse
WHERE metric_month = (SELECT metric_month FROM latest)
GROUP BY community_area_name
HAVING MEASURE(total_311_requests) >= 3000
   AND MEASURE(total_building_violations) >= 100
ORDER BY total_311_requests DESC, total_building_violations DESC
```

## 22. Which Community Areas had more than 3,000 311 requests but fewer than 20 business license issues in the last completed month?

Category: Cross-dataset reasoning

```sql
WITH latest AS (SELECT MAX(metric_month) AS metric_month FROM workspace.chicagopulse.mv_neighborhood_pulse)
SELECT community_area_name,
       MEASURE(total_311_requests) AS total_311_requests,
       MEASURE(total_business_license_issues) AS total_business_license_issues
FROM workspace.chicagopulse.mv_neighborhood_pulse
WHERE metric_month = (SELECT metric_month FROM latest)
GROUP BY community_area_name
HAVING MEASURE(total_311_requests) > 3000
   AND MEASURE(total_business_license_issues) IS NOT NULL
   AND MEASURE(total_business_license_issues) < 20
ORDER BY total_311_requests DESC
```

## 23. Which Community Areas had both 311 requests and building violations increase by more than 10 percent in the latest completed month?

Category: Cross-dataset reasoning

```sql
WITH monthly AS (
  SELECT metric_month, community_area_name,
         MEASURE(request_mom_change_pct) AS request_mom_change_pct,
         MEASURE(violation_mom_change_pct) AS violation_mom_change_pct
  FROM workspace.chicagopulse.mv_neighborhood_pulse
  GROUP BY metric_month, community_area_name
),
latest AS (SELECT MAX(metric_month) AS metric_month FROM monthly)
SELECT community_area_name,
       request_mom_change_pct,
       violation_mom_change_pct
FROM monthly
WHERE metric_month = (SELECT metric_month FROM latest)
  AND request_mom_change_pct > 10
  AND violation_mom_change_pct > 10
ORDER BY request_mom_change_pct DESC, violation_mom_change_pct DESC
```

## 24. Show the 10 Community Areas with the most building permits in the last completed month and include their building violation counts.

Category: Cross-dataset reasoning

```sql
WITH latest AS (SELECT MAX(metric_month) AS metric_month FROM workspace.chicagopulse.mv_neighborhood_pulse)
SELECT community_area_name,
       MEASURE(total_building_permits) AS total_building_permits,
       MEASURE(total_building_violations) AS total_building_violations
FROM workspace.chicagopulse.mv_neighborhood_pulse
WHERE metric_month = (SELECT metric_month FROM latest)
GROUP BY community_area_name
HAVING MEASURE(total_building_permits) IS NOT NULL
ORDER BY total_building_permits DESC
LIMIT 10
```

## 25. For the 10 Community Areas with the most 311 requests in the last completed month, show 311 requests, building violations, building permits, and business license issues.

Category: Cross-dataset reasoning

```sql
WITH latest AS (SELECT MAX(metric_month) AS metric_month FROM workspace.chicagopulse.mv_neighborhood_pulse)
SELECT community_area_name,
       MEASURE(total_311_requests) AS total_311_requests,
       MEASURE(total_building_violations) AS total_building_violations,
       MEASURE(total_building_permits) AS total_building_permits,
       MEASURE(total_business_license_issues) AS total_business_license_issues
FROM workspace.chicagopulse.mv_neighborhood_pulse
WHERE metric_month = (SELECT metric_month FROM latest)
GROUP BY community_area_name
ORDER BY total_311_requests DESC
LIMIT 10
```

## 26. Which Community Areas had more building violations than building permits in the last completed month?

Category: Cross-dataset reasoning

```sql
WITH latest AS (SELECT MAX(metric_month) AS metric_month FROM workspace.chicagopulse.mv_neighborhood_pulse)
SELECT community_area_name,
       MEASURE(total_building_violations) AS total_building_violations,
       MEASURE(total_building_permits) AS total_building_permits
FROM workspace.chicagopulse.mv_neighborhood_pulse
WHERE metric_month = (SELECT metric_month FROM latest)
GROUP BY community_area_name
HAVING MEASURE(total_building_violations) IS NOT NULL
   AND MEASURE(total_building_permits) IS NOT NULL
   AND MEASURE(total_building_violations) > MEASURE(total_building_permits)
ORDER BY total_building_violations DESC
```

## 27. Which Community Areas had at least 50 building violations but fewer than 10 building permits in the last completed month?

Category: Cross-dataset reasoning

```sql
WITH latest AS (SELECT MAX(metric_month) AS metric_month FROM workspace.chicagopulse.mv_neighborhood_pulse)
SELECT community_area_name,
       MEASURE(total_building_violations) AS total_building_violations,
       MEASURE(total_building_permits) AS total_building_permits
FROM workspace.chicagopulse.mv_neighborhood_pulse
WHERE metric_month = (SELECT metric_month FROM latest)
GROUP BY community_area_name
HAVING MEASURE(total_building_violations) >= 50
   AND MEASURE(total_building_permits) IS NOT NULL
   AND MEASURE(total_building_permits) < 10
ORDER BY total_building_violations DESC
```

## 28. When was each ChicagoPulse dataset last ingested?

Category: Freshness and coverage

```sql
SELECT dataset, last_ingested_at
FROM workspace.chicagopulse.gold_data_freshness
ORDER BY dataset
```

## 29. How many rows does ChicagoPulse currently have for each source dataset?

Category: Freshness and coverage

```sql
SELECT dataset, row_count
FROM workspace.chicagopulse.gold_data_freshness
ORDER BY dataset
```

## 30. What date range is stored for each ChicagoPulse source dataset?

Category: Freshness and coverage

```sql
SELECT dataset, min_date, max_date
FROM workspace.chicagopulse.gold_data_freshness
ORDER BY dataset
```
