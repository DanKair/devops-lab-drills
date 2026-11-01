resource "docker_container" "api" {
  name  = "tf-api"
  image = docker_image.nginx.id_image

  ports {
    internal = 80
    external = var.api_port
  }
}

output "api_url" {
  value = "http://localhost:${docker_container.api.ports.external}"
}
