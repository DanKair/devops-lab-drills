# DevOps Lab Drills homelab: control + node1 + node2 on a VirtualBox host-only network.
# Needs ~5.5 GB free RAM. The repo folder is synced to /vagrant, and the `lab` CLI
# is installed on control in editable mode, so edits to labs/ apply immediately.
Vagrant.configure("2") do |config|
  config.vm.box = "bento/ubuntu-24.04"

  machines = {
    "control" => { ip: "192.168.56.10", mem: 2048 },
    "node1"   => { ip: "192.168.56.11", mem: 2048 },
    "node2"   => { ip: "192.168.56.12", mem: 1536 },
  }

  machines.each do |name, spec|
    config.vm.define name do |m|
      m.vm.hostname = name
      m.vm.network "private_network", ip: spec[:ip]
      m.vm.provider "virtualbox" do |vb|
        vb.name   = "lab-#{name}"
        vb.memory = spec[:mem]
        vb.cpus   = 2
      end
      # Password SSH stays on so ans-01 can teach ssh-copy-id. sshd uses the first
      # value it reads and drop-ins load alphabetically, hence the 00- prefix.
      m.vm.provision "shell", inline: <<-SHELL
        echo "PasswordAuthentication yes" > /etc/ssh/sshd_config.d/00-lab.conf
        systemctl restart ssh
        grep -q lab-hosts /etc/hosts || printf '%s\n' '# lab-hosts' \
          '192.168.56.10 control' '192.168.56.11 node1' '192.168.56.12 node2' >> /etc/hosts
      SHELL
      if name == "control"
        m.vm.provision "shell", inline: <<-SHELL
          apt-get update
          apt-get install -y ansible git curl jq pipx
          sudo -u vagrant -H bash -lc 'pipx ensurepath && pipx install --force --editable /vagrant'
          echo "Done. Next: vagrant ssh control, then run: lab doctor"
        SHELL
      end
    end
  end
end
