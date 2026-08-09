output "bootstrap_brokers_tls" {
  value = aws_msk_cluster.main.bootstrap_brokers_tls
}

output "bootstrap_brokers_public_tls" {
  value = aws_msk_cluster.main.bootstrap_brokers_public_tls
}

output "zookeeper_connect_string" {
  value = aws_msk_cluster.main.zookeeper_connect_string
}