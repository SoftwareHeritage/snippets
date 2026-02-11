
update listers
set name='forgejo'
where name='gitea' and instance_name='git.bobc.io';

update task set type='list-forgejo-full'
where type='list-gitea-full' and
      (
        arguments#>>'{kwargs,instance}'='git.bobc.io' or
        arguments#>>'{kwargs,url}'='https://git.bobc.io/' or
        arguments#>>'{kwargs,url}' ~ 'https://git.bobc.io.*/.*api/v1/'
      );

update listers
set name='forgejo'
where name='gitea' and instance_name='git.koha-community.org';

update task set type='list-forgejo-full'
where type='list-gitea-full' and
      (
        arguments#>>'{kwargs,instance}'='git.koha-community.org' or
        arguments#>>'{kwargs,url}'='https://git.koha-community.org/' or
        arguments#>>'{kwargs,url}' ~ 'https://git.koha-community.org.*/.*api/v1/'
      );

update listers
set name='forgejo'
where name='gitea' and instance_name='git.imirhil.fr';

update task set type='list-forgejo-full'
where type='list-gitea-full' and
      (
        arguments#>>'{kwargs,instance}'='git.imirhil.fr' or
        arguments#>>'{kwargs,url}'='https://git.imirhil.fr/' or
        arguments#>>'{kwargs,url}' ~ 'https://git.imirhil.fr.*/.*api/v1/'
      );

update listers
set name='forgejo'
where name='gitea' and instance_name='gitea.angry.im';

update task set type='list-forgejo-full'
where type='list-gitea-full' and
      (
        arguments#>>'{kwargs,instance}'='gitea.angry.im' or
        arguments#>>'{kwargs,url}'='https://gitea.angry.im/' or
        arguments#>>'{kwargs,url}' ~ 'https://gitea.angry.im.*/.*api/v1/'
      );

update listers
set name='forgejo'
where name='gitea' and instance_name='git.asgardius.company';

update task set type='list-forgejo-full'
where type='list-gitea-full' and
      (
        arguments#>>'{kwargs,instance}'='git.asgardius.company' or
        arguments#>>'{kwargs,url}'='https://git.asgardius.company/' or
        arguments#>>'{kwargs,url}' ~ 'https://git.asgardius.company.*/.*api/v1/'
      );

update listers
set name='forgejo'
where name='gitea' and instance_name='git.data.coop';

update task set type='list-forgejo-full'
where type='list-gitea-full' and
      (
        arguments#>>'{kwargs,instance}'='git.data.coop' or
        arguments#>>'{kwargs,url}'='https://git.data.coop/' or
        arguments#>>'{kwargs,url}' ~ 'https://git.data.coop.*/.*api/v1/'
      );

update listers
set name='forgejo'
where name='gitea' and instance_name='code.blicky.net';

update task set type='list-forgejo-full'
where type='list-gitea-full' and
      (
        arguments#>>'{kwargs,instance}'='code.blicky.net' or
        arguments#>>'{kwargs,url}'='https://code.blicky.net/' or
        arguments#>>'{kwargs,url}' ~ 'https://code.blicky.net.*/.*api/v1/'
      );

update listers
set name='forgejo'
where name='gitea' and instance_name='git.rjp.is';

update task set type='list-forgejo-full'
where type='list-gitea-full' and
      (
        arguments#>>'{kwargs,instance}'='git.rjp.is' or
        arguments#>>'{kwargs,url}'='https://git.rjp.is/' or
        arguments#>>'{kwargs,url}' ~ 'https://git.rjp.is.*/.*api/v1/'
      );

update listers
set name='forgejo'
where name='gitea' and instance_name='git.0x90.space';

update task set type='list-forgejo-full'
where type='list-gitea-full' and
      (
        arguments#>>'{kwargs,instance}'='git.0x90.space' or
        arguments#>>'{kwargs,url}'='https://git.0x90.space/' or
        arguments#>>'{kwargs,url}' ~ 'https://git.0x90.space.*/.*api/v1/'
      );

update listers
set name='forgejo'
where name='gitea' and instance_name='git.disroot.org';

update task set type='list-forgejo-full'
where type='list-gitea-full' and
      (
        arguments#>>'{kwargs,instance}'='git.disroot.org' or
        arguments#>>'{kwargs,url}'='https://git.disroot.org/' or
        arguments#>>'{kwargs,url}' ~ 'https://git.disroot.org.*/.*api/v1/'
      );

update listers
set name='forgejo'
where name='gitea' and instance_name='git.froggi.es';

update task set type='list-forgejo-full'
where type='list-gitea-full' and
      (
        arguments#>>'{kwargs,instance}'='git.froggi.es' or
        arguments#>>'{kwargs,url}'='https://git.froggi.es/' or
        arguments#>>'{kwargs,url}' ~ 'https://git.froggi.es.*/.*api/v1/'
      );

update listers
set name='forgejo'
where name='gitea' and instance_name='git.g3la.de';

update task set type='list-forgejo-full'
where type='list-gitea-full' and
      (
        arguments#>>'{kwargs,instance}'='git.g3la.de' or
        arguments#>>'{kwargs,url}'='https://git.g3la.de/' or
        arguments#>>'{kwargs,url}' ~ 'https://git.g3la.de.*/.*api/v1/'
      );
