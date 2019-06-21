FROM python:3.7
MAINTAINER Viachaslau Tsypylou "viachaslau_tsypylou@epam.com"
COPY ./aws_instance_scheduler /app
WORKDIR /app
RUN pip3 install -r requirements.txt
ENV LC_ALL=C.UTF-8
ENV LANG=C.UTF-8
CMD flask run --host 0.0.0.0