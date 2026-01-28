# Bot de scraping internet pour notifier de la présence.
Lors de mon parcours scolaire à l'ESILV, un des principaux problèmes que j'ai rencontré était les absences. Non pas parce que je n'allais pas en cours, mais parce que le système de présence était différent de ce que j'avais connu. Ainsi, lorsque le professeur "ouvrait" l'appel sur son portail, les étudiants pouvaient à leur tour se mettre présent depuis leur application. Mais il suffit d'un oubli, ou d'un professeur qui ne communique pas sur l'ouverture de la présence pour se retrouver avec une absence alors que j'étais présent au cours.

Pour prévenir cela, j'ai décidé de créer un rapide script python qui se connecte avec mes identifiants, et qui actualise en continu les pages de cours pour détecter si la présence est ouverte et me notifie via un bot discord lorsque c'est le cas. Pour cela, j'ai utilisé les librairies selenium et BeautifulSoup pour faire du scraping sur le site de mon école.

Le bot est adaptable pour n'importe quel étudiant du pôle Leonard de Vinci, il suffit juste de le faire tourner en local. C'est pour cela que j'ai installé un setup avec un Raspberry Pi 4 afin d'héberger le script python moi même pour qu'il tourne de façon continue, mais aussi pour héberger plusieurs autres projets personnels.

Le script se décline en deux versions, une pour faire tourner le bot sur un environnemnt linux en headless (idéal pour un raspberry), l'autre sur windows, où l'on voit les actions réalisées par le script (connexion sur la page, navigation sur les différents cours).
