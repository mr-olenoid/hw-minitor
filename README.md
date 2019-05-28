# hw_exporter
Hardware server metric exporter using redfish for prometheus (main.py)
or push alerts and worning into RabbitMQ (developed to be deployed in container)

System variables:
-e RABBIT_ADDRESS=''
-e RABBIT_PORT=''
-e RABBIT_USER=''
-e RABBIT_PASSWORD=''
-e DB_ADDRESS=''
-e DB_USER=''
-e DB_PASSWORD=''
-e DB_NAME=''
-e REDFISH_USER=''
-e REDFISH_PASSWORD=''
