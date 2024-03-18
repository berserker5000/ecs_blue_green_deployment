FROM python:3.11.7-alpine
LABEL authors="dmytro.kulyk@cognitran.com"
RUN pip install --no-cache-dir boto3
COPY autoscaling_ec2.py /tmp/
COPY database.py /tmp/
COPY ecs.py /tmp/
COPY bg.py /tmp/main.py
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
#ENTRYPOINT ["/entrypoint.sh"]
CMD ["python","-u","/tmp/main.py"]