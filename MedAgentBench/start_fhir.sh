#First-time setup
sudo usermod -aG docker $USER
docker pull hapiproject/hapi:latest


cd MedAgentBench-dev
docker run -p 8080:8080 -v $(pwd)/:/configs -e "--spring.config.location=file:///configs/application.yaml" -v /home/yx/my_h2_data:/data  hapiproject/hapi:latest


