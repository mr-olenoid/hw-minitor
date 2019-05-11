CREATE TABLE `hardwareServers` (
  `name` varchar(20) NOT NULL,
  `server_ip` varchar(20) DEFAULT NULL,
  `tag` varchar(40) NOT NULL,
  `id` varchar(100) NOT NULL,
  `real_name` varchar(100) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8;
