output "kafka_public_ip" {
  value = aws_instance.kafka.public_ip
}

output "kafka_instance_id" {
  value = aws_instance.kafka.id
}