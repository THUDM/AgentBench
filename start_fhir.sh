cd MedAgentBench-dev

docker run -d -p 8080:8080 -v $(pwd)/:/configs -e "--spring.config.location=file:///configs/application.yaml" -v /home/yx/my_h2_data:/data  hapiproject/hapi:latest


