FROM python:3.11.7-alpine
LABEL authors="dmytro.kulyk@cognitran.com"
RUN pip install --no-cache-dir boto3@1.26.151
COPY *.py /tmp/
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
ENTRYPOINT ["/entrypoint.sh"]