# List of chosen technologies
- Flask
  - Lightweight: Flask is a minimalistic web framework that’s easy to set up and extend
  - WebSocket Support: Flask-SocketIO provides seamless WebSocket support for real-time interactions, crucial for leaderboard updates and quiz participation
  - Ease of Use: Python and Flask offer a rich ecosystem of libraries, making them ideal for rapid development
    <br><br>
- Amazon Managed Streaming for Apache Kafka (MSK)
  - Scalable: MSK can handle high volumes of messages, ensuring that the system can scale to support a large number of concurrent users
  - Reliable: MSK provides a managed Kafka service with built-in features for high availability and fault tolerance
  - Cost-effective: MSK eliminates the need to manage Kafka clusters, reducing operational overhead and costs
<br><br>
- Amazon ElastiCache for Redis
  - Low Latency: Redis is an in-memory data store that provides sub-millisecond latency, ideal for leaderboard caching
  - Scalability: Amazon ElastiCache can scale horizontally to handle a growing number of leaderboard updates and queries
<br><br>
- Amazon DynamoDB
  - High Scalability: DynamoDB can handle large volumes of concurrent reads and writes, making it suitable for storing user scores
  - Low Operational Overhead: Being fully managed by AWS, DynamoDB eliminates the need for database maintenance
  - High Availability: Multi-AZ replication ensures data is always available
<br><br>
- AWS Elastic Kubernetes Service (EKS)
  - Scalability and High Availability: Kubernetes orchestrates containers across multiple nodes and availability zones
  - Managed by AWS: AWS takes care of the control plane, simplifying cluster management
<br><br>
- AWS Application Load Balancer (ALB)
  - Traffic Distribution: ALB efficiently distributes incoming WebSocket and HTTP traffic to the Kubernetes cluster
  - Autoscaling Integration: ALB integrates with Kubernetes and EKS, allowing dynamic scaling based on traffic
<br><br>
# Monitoring and Observability
- AWS CloudWatch
  - Centralized Monitoring: Collects and aggregates logs and metrics from all system components (WebSocket servers, Kafka, Redis, DynamoDB, EKS, ALB).
  - Real-Time Alerts: Sends notifications when predefined thresholds (e.g., high memory usage or increased response times) are breached
  - Integration with AWS Services: Provides a unified view of all AWS services, simplifying debugging and performance tuning
  - Searching, filtering, and visualizing logs for debugging
  - Dashboard for Key Metrics
    - Display metrics for WebSocket servers (active connections, message latency).
    - Display metrics for Kafka (producer and consumer lag).
    - Display metrics for Redis (memory usage, hit rate, latency).
    - Display metrics for DynamoDB (read and write capacity units, latency).
    - Display metrics for EKS (CPU, memory, and network utilization).
    - Display metrics for ALB (request count, latency, and error rate).
<br><br>
- Grafana
  - If additional flexibility is needed, integrate Grafana with CloudWatch for advanced dashboarding and alerting capabilities
<br><br>
- Alert and Notification
  - CloudWatch Alarms trigger alerts based on predefined thresholds
  - SNS (Simple Notification Service) sends SMS notifications to team members when alarms are triggered
