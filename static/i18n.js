'use strict';
// Gemeinsamer Übersetzungskatalog: Deutsch dient als stabiler Schlüssel.
// Reihenfolge der Übersetzungen: Englisch, Französisch, Spanisch.
const I18N = (() => {
  const texts = {
    'Sprache':['Language','Langue','Idioma'],
    'Hauptnavigation':['Main navigation','Navigation principale','Navegación principal'],
    'Home':['Home','Accueil','Inicio'],
    'Einstellungen':['Settings','Paramètres','Ajustes'],
    'Demonstrationsmodus':['Demo mode','Mode démo','Modo demostración'],
    'Virtuelle Wallbox':['Virtual wallbox','Borne virtuelle','Cargador virtual'],
    'Alle Messwerte und Ladevorgänge sind fiktiv. Keine reale Hardware verbunden.':['All readings and charging sessions are simulated. No real hardware is connected.','Toutes les mesures et sessions de recharge sont fictives. Aucun matériel réel connecté.','Todas las mediciones y sesiones de carga son simuladas. No hay hardware real conectado.'],
    'Fahrzeug trennen':['Disconnect vehicle','Débrancher le véhicule','Desconectar vehículo'],
    'Wallbox und Fahrzeug':['Wallbox and vehicle','Borne et véhicule','Cargador y vehículo'],
    'HEIMLADESTATION':['HOME CHARGING STATION','BORNE À DOMICILE','ESTACIÓN DE CARGA DOMÉSTICA'],
    'Verbinde …':['Connecting …','Connexion …','Conectando …'],
    'Wallbox ohne Fahrzeug':['Wallbox without vehicle','Borne sans véhicule','Cargador sin vehículo'],
    'Aktueller Nutzer':['Current user','Utilisateur actuel','Usuario actual'],
    'Niemand':['None','Aucun','Ninguno'],
    'Livewerte':['Live readings','Mesures en direct','Mediciones en directo'],
    'Ladeleistung':['Charging power','Puissance de recharge','Potencia de carga'],
    'Fahrzeug':['Vehicle','Véhicule','Vehículo'],
    'Wallbox-Status':['Wallbox status','État de la borne','Estado del cargador'],
    'Ladevorgang starten':['Start charging','Démarrer la recharge','Iniciar carga'],
    'Ladevorgang stoppen':['Stop charging','Arrêter la recharge','Detener carga'],
    'LADESTART GEPLANT':['CHARGING SCHEDULED','RECHARGE PROGRAMMÉE','CARGA PROGRAMADA'],
    'AUTOMATIK · GEPLANTER LADESTART':["AUTO · SCHEDULED CHARGING START","AUTO · DÉMARRAGE DE RECHARGE PRÉVU","AUTO · INICIO DE CARGA PREVISTO"],
    'Diesen Ladestart überspringen':["Skip this charging start","Ignorer ce démarrage de recharge","Omitir este inicio de carga"],
    'Überspringen rückgängig machen':["Undo skip","Annuler l’omission","Deshacer omisión"],
    'Ladestart ausgesetzt:':["Charging start skipped:","Démarrage suspendu :","Inicio de carga omitido:"],
    'Dieser Ladestart wird ausgelassen':["This charging start will be skipped","Ce démarrage de recharge sera ignoré","Se omitirá este inicio de carga"],
    'Nur dieser Termin entfällt. Die tägliche Automatik bleibt aktiv.':["Only this occurrence is skipped. Daily automatic charging remains enabled.","Seul ce créneau est ignoré. La recharge automatique quotidienne reste activée.","Solo se omite esta ocasión. La carga automática diaria sigue activa."],
    'Zur gewählten Uhrzeit wird geladen, wenn ein Fahrzeug angeschlossen ist und die Wallbox laden kann.':["At the selected time, charging starts if a vehicle is connected and the charger is ready.","À l’heure choisie, la recharge démarre si un véhicule est branché et que la borne est disponible.","A la hora seleccionada, la carga comienza si hay un vehículo conectado y el cargador está disponible."],
    'Automatischer Ladestart wieder aktiviert.':["Automatic charging start restored.","Démarrage automatique rétabli.","Inicio de carga automático restaurado."],
    'Ist zur gewählten Uhrzeit kein Fahrzeug angeschlossen oder bereits eine andere Ladung aktiv oder geplant, wird nicht gestartet. Es erfolgt kein nachträglicher Start beim Anstecken.':["At the selected time, charging will not start if no vehicle is connected or another session is active or scheduled. Connecting a vehicle later will not trigger a delayed start.","À l’heure choisie, la recharge ne démarre pas si aucun véhicule n’est branché ou si une autre recharge est en cours ou programmée. Un branchement ultérieur ne déclenche pas de recharge.","A la hora seleccionada, la carga no empieza si no hay un vehículo conectado o si hay otra sesión activa o programada. Conectar un vehículo más tarde no provoca un inicio retrasado."],
    'LADESTEUERUNG':['CHARGING CONTROL','COMMANDE DE RECHARGE','CONTROL DE CARGA'],
    'Ladeleistung einstellen':['Set charging power','Régler la puissance','Ajustar potencia de carga'],
    'bis 11 kW':['up to 11 kW','jusqu’à 11 kW','hasta 11 kW'],
    '5,5':['5.5','5,5','5,5'],
    'Nur während der Ladung einstellbar.':['Adjustable only while charging.','Réglable uniquement pendant la recharge.','Solo ajustable durante la carga.'],
    'MONITORING':['MONITORING','MESURES','MONITORIZACIÓN'],
    'Elektrische Messwerte':['Electrical readings','Mesures électriques','Mediciones eléctricas'],
    'Energie gesamt':['Total energy','Énergie totale','Energía total'],
    'PCB-Temperatur':['PCB temperature','Température du circuit','Temperatura de la placa'],
    'Spannung':['Voltage','Tension','Tensión'],
    'Strom':['Current','Courant','Corriente'],
    'LADEHISTORIE':['CHARGING HISTORY','HISTORIQUE DE RECHARGE','HISTORIAL DE CARGA'],
    'Alle Ladevorgänge':['All charging sessions','Toutes les sessions','Todas las sesiones de carga'],
    'Monatssummen · abgeschlossene Ladungen':['Monthly totals · completed sessions','Totaux mensuels · sessions terminées','Totales mensuales · sesiones finalizadas'],
    'Monatssummen · abgeschlossene Ladungen · Fiktive Beispieldaten':['Monthly totals · completed sessions · Simulated example data','Totaux mensuels · sessions terminées · Données fictives','Totales mensuales · sesiones finalizadas · Datos ficticios'],
    'Lade Historie …':['Loading history …','Chargement de l’historique …','Cargando historial …'],
    'KONFIGURATION':['CONFIGURATION','CONFIGURATION','CONFIGURACIÓN'],
    'Einstellungsbereiche':['Settings sections','Rubriques des paramètres','Secciones de ajustes'],
    'Personen & Bilder':['People & images','Personnes et images','Personas e imágenes'],
    'Automatik':['Automatic charging','Recharge automatique','Carga automática'],
    'Kosten':['Costs','Coûts','Costes'],
    'PERSONENVERWALTUNG':['PEOPLE MANAGEMENT','GESTION DES PERSONNES','GESTIÓN DE PERSONAS'],
    'Personen & Fahrzeugbilder':['People & vehicle images','Personnes et images des véhicules','Personas e imágenes de vehículos'],
    'Person hinzufügen':['Add person','Ajouter une personne','Añadir persona'],
    '+ Person hinzufügen':['+ Add person','+ Ajouter une personne','+ Añadir persona'],
    'Personen hinzufügen und bei Bedarf ein eigenes Fahrzeugbild hinterlegen. JPG, PNG oder WebP · maximal 8 MB · Querformat empfohlen':['Add people and optionally save their own vehicle image. JPG, PNG or WebP · max. 8 MB · landscape recommended','Ajoutez des personnes et, si souhaité, une image de leur véhicule. JPG, PNG ou WebP · 8 Mo max. · format paysage conseillé','Añade personas y, si lo deseas, una imagen de su vehículo. JPG, PNG o WebP · máximo 8 MB · formato horizontal recomendado'],
    'LADEAUTOMATIK':['AUTOMATIC CHARGING','RECHARGE AUTOMATIQUE','CARGA AUTOMÁTICA'],
    'Automatischer Start':['Automatic start','Démarrage automatique','Inicio automático'],
    'Automatik aktivieren':['Enable automatic charging','Activer la recharge automatique','Activar carga automática'],
    'Zur gewählten Uhrzeit wird geprüft, ob ein Fahrzeug angeschlossen ist. Ist es angeschlossen und die Wallbox bereit, startet die Ladung automatisch.':["At the selected time, the wallbox checks whether a vehicle is connected. If it is connected and the charger is ready, charging starts automatically.","À l’heure choisie, la borne vérifie si un véhicule est branché. Si le véhicule est branché et que la borne est prête, la recharge démarre automatiquement.","A la hora seleccionada, el cargador comprueba si hay un vehículo conectado. Si está conectado y el cargador está listo, la carga comienza automáticamente."],
    'Tägliche Ladezeit':["Daily charging time","Heure de recharge quotidienne","Hora diaria de carga"],
    'Deutsche Ortszeit':['German local time','Heure locale allemande','Hora local de Alemania'],
    'Startstunde':['Start hour','Heure de démarrage','Hora de inicio'],
    '01:00 Uhr':['01:00','01:00','01:00'],
    'Automatischer Ladestart bei angeschlossenem Fahrzeug':["Automatic start if a vehicle is connected","Démarrage automatique si un véhicule est branché","Inicio automático si hay un vehículo conectado"],
    'Standardperson':['Default person','Personne par défaut','Persona predeterminada'],
    'Automatik speichern':['Save automatic charging','Enregistrer la recharge automatique','Guardar carga automática'],
    'STROMTARIF':['ELECTRICITY RATE','TARIF D’ÉLECTRICITÉ','TARIFA ELÉCTRICA'],
    'Stromkosten':['Electricity costs','Coût de l’électricité','Costes eléctricos'],
    'Aktueller Strompreis':['Current electricity rate','Tarif d’électricité actuel','Tarifa eléctrica actual'],
    'Arbeitspreis':['Energy rate','Prix de l’énergie','Precio de la energía'],
    '26,00':['26.00','26,00','26,00'],
    'Gilt ab der nächsten Ladung.':['Applies from the next session.','Applicable dès la prochaine recharge.','Se aplica desde la próxima carga.'],
    'Strompreis speichern':['Save electricity rate','Enregistrer le tarif','Guardar tarifa eléctrica'],
    'Lokale Steuerung':['Local control','Commande locale','Control local'],
    'Person auswählen':['Select person','Choisir une personne','Seleccionar persona'],
    'Schließen':['Close','Fermer','Cerrar'],
    'Fahrzeugvorschau':['Vehicle preview','Aperçu du véhicule','Vista previa del vehículo'],
    'Person':['Person','Personne','Persona'],
    'Startmodus':['Start mode','Mode de démarrage','Modo de inicio'],
    'Sofort laden':['Charge now','Recharger maintenant','Cargar ahora'],
    'Jetzt freigeben':['Enable now','Autoriser maintenant','Habilitar ahora'],
    'Zeit wählen':['Choose time','Choisir l’heure','Elegir hora'],
    'Automatisch starten':['Start automatically','Démarrer automatiquement','Iniciar automáticamente'],
    'Startzeit':['Start time','Heure de démarrage','Hora de inicio'],
    'Ortszeit Deutschland':['German local time','Heure locale allemande','Hora local de Alemania'],
    'Volle Stunde auswählen':['Select an hour','Choisir une heure pleine','Seleccionar una hora en punto'],
    'Wähle eine Uhrzeit.':['Choose a time.','Choisissez une heure.','Elige una hora.'],
    'Fahrzeug angeschlossen lassen.':['Keep the vehicle connected.','Laissez le véhicule branché.','Deja el vehículo conectado.'],
    'Abbrechen':['Cancel','Annuler','Cancelar'],
    'Weiter':['Next','Suivant','Siguiente'],
    'Name':['Name','Nom','Nombre'],
    'z. B. Alex':['e.g. Alex','p. ex. Alex','p. ej., Alex'],
    'Die Person wird für die Ladeauswahl, Ladehistorie und Automatik gespeichert. Ein Fahrzeugbild kann anschließend ergänzt werden.':['The person is saved for charging selection, history and automatic charging. A vehicle image can be added afterwards.','La personne est enregistrée pour la sélection, l’historique et la recharge automatique. Une image du véhicule pourra être ajoutée ensuite.','La persona se guarda para la selección, el historial y la carga automática. Después se puede añadir una imagen del vehículo.'],
    'Hinzufügen':['Add','Ajouter','Añadir'],
    'Person löschen?':['Delete person?','Supprimer la personne ?','¿Eliminar persona?'],
    'Möchtest du':['Do you want to permanently delete','Voulez-vous supprimer définitivement','¿Quieres eliminar permanentemente a'],
    'und das zugehörige Fahrzeugbild dauerhaft entfernen?':['and the associated vehicle image?','et l’image du véhicule associée ?','y la imagen del vehículo asociado?'],
    'Bisherige Ladevorgänge bleiben einschließlich der Namen und Kosten in der Historie erhalten. Ist die Person für die Ladeautomatik ausgewählt, wird diese deaktiviert.':['Past charging sessions, names and costs remain in the history. If this person is set for automatic charging, it will be disabled.','Les sessions passées, noms et coûts restent dans l’historique. Si cette personne est sélectionnée pour la recharge automatique, celle-ci sera désactivée.','Las sesiones anteriores, nombres y costes se conservan en el historial. Si esta persona está asignada a la carga automática, se desactivará.'],
    'Person löschen':['Delete person','Supprimer la personne','Eliminar persona'],
    'Ungültige Serverantwort ({status}).':['Invalid server response ({status}).','Réponse serveur invalide ({status}).','Respuesta del servidor no válida ({status}).'],
    'Anfrage fehlgeschlagen':['Request failed','Échec de la requête','Error en la solicitud'],
    'Webserver nicht erreichbar.':['Web server unreachable.','Serveur web inaccessible.','Servidor web inaccesible.'],
    'Fahrzeug an einer Wallbox':['Vehicle at a wallbox','Véhicule à une borne','Vehículo en un cargador'],
    'Persönliches Fahrzeug':['Personal vehicle','Véhicule personnel','Vehículo personal'],
    'Verbindungsstatus unbekannt':['Connection status unknown','État de connexion inconnu','Estado de conexión desconocido'],
    'Kein Fahrzeugbild hinterlegt':['No vehicle image saved','Aucune image de véhicule enregistrée','Sin imagen de vehículo guardada'],
    '(geplant)':['(scheduled)','(programmé)','(programado)'],
    'Personen werden geladen …':['Loading people …','Chargement des personnes …','Cargando personas …'],
    'Noch keine Personen angelegt. Über „Person hinzufügen“ kannst du die erste Person erstellen.':['No people added yet. Use “Add person” to create the first profile.','Aucune personne ajoutée. Utilisez « Ajouter une personne » pour créer le premier profil.','Aún no hay personas. Usa «Añadir persona» para crear el primer perfil.'],
    'Fahrzeug von':['Vehicle of','Véhicule de','Vehículo de'],
    'Eigenes Bild hinterlegt':['Custom image saved','Image personnelle enregistrée','Imagen personalizada guardada'],
    'Fahrzeugbild für':['Vehicle image for','Image du véhicule de','Imagen del vehículo de'],
    'Speichern':['Save','Enregistrer','Guardar'],
    'Bild entfernen':['Remove image','Supprimer l’image','Eliminar imagen'],
    'Datei zu groß (maximal 8 MB).':['File too large (maximum 8 MB).','Fichier trop volumineux (8 Mo max.).','Archivo demasiado grande (máximo 8 MB).'],
    'Vorschau – noch nicht gespeichert':['Preview – not yet saved','Aperçu – pas encore enregistré','Vista previa – aún no guardada'],
    'Wird gespeichert …':['Saving …','Enregistrement …','Guardando …'],
    'Bild entfernt.':['Image removed.','Image supprimée.','Imagen eliminada.'],
    'Bild gespeichert.':['Image saved.','Image enregistrée.','Imagen guardada.'],
    'Person löschen:':['Delete person:','Supprimer la personne :','Eliminar persona:'],
    'Bitte einen Namen eingeben.':['Please enter a name.','Veuillez saisir un nom.','Introduce un nombre.'],
    'wurde hinzugefügt.':['was added.','a été ajouté(e).','se ha añadido.'],
    'Wird gelöscht …':['Deleting …','Suppression …','Eliminando …'],
    'gelöscht. Ladeautomatik deaktiviert.':['deleted. Automatic charging disabled.','supprimé(e). Recharge automatique désactivée.','eliminado/a. Carga automática desactivada.'],
    'wurde gelöscht.':['was deleted.','a été supprimé(e).','se ha eliminado.'],
    'Strompreis gespeichert.':['Electricity rate saved.','Tarif enregistré.','Tarifa eléctrica guardada.'],
    ':00 Uhr':[':00',':00',':00'],
    'Keine Personen vorhanden.':['No people available.','Aucune personne disponible.','No hay personas disponibles.'],
    'Standardperson neu wählen.':['Select a new default person.','Choisissez une nouvelle personne par défaut.','Selecciona otra persona predeterminada.'],
    'Einstellungen werden geladen …':['Loading settings …','Chargement des paramètres …','Cargando ajustes …'],
    'Automatik gespeichert.':['Automatic charging saved.','Recharge automatique enregistrée.','Carga automática guardada.'],
    'Automatik aus':['Automatic charging off','Recharge automatique désactivée','Carga automática desactivada'],
    'Nächster automatischer Ladestart:':["Next automatic start:","Prochain démarrage automatique :","Próximo inicio automático:"],
    'Automatischer Ladestart aktiv':["Automatic charging enabled","Démarrage automatique activé","Inicio automático activado"],
    'Standardperson:':['Default person:','Personne par défaut :','Persona predeterminada:'],
    'Keine Verbindung':['No connection','Aucune connexion','Sin conexión'],
    'Zeitpunkt für automatischen Ladestart':["Automatic charging time reached","Heure de recharge automatique atteinte","Hora de carga automática alcanzada"],
    'Ladestart in {hours} Std. {minutes} Min.':["Charging starts in {hours} h {minutes} min","Démarrage dans {hours} h {minutes} min","Inicio de carga en {hours} h {minutes} min"],
    'Ladestart einmalig übersprungen.':["Charging start skipped once.","Démarrage ignoré pour cette fois.","Inicio de carga omitido una vez."],
    'Bitte eine Person wählen.':['Please select a person.','Veuillez choisir une personne.','Selecciona una persona.'],
    'Noch keine Personen vorhanden. Lege zuerst eine Person an.':['No people yet. Add a person first.','Aucune personne. Ajoutez-en une d’abord.','Aún no hay personas. Añade una primero.'],
    'Jetzt starten':['Start now','Démarrer maintenant','Iniciar ahora'],
    'Start planen':['Schedule start','Programmer le démarrage','Programar inicio'],
    'Heute':['Today','Aujourd’hui','Hoy'],
    'Morgen':['Tomorrow','Demain','Mañana'],
    'Wann soll geladen werden?':['When should charging start?','Quand faut-il recharger ?','¿Cuándo quieres cargar?'],
    '2 von 2 ·':['2 of 2 ·','2 sur 2 ·','2 de 2 ·'],
    'Zurück':['Back','Retour','Atrás'],
    'Fahrzeug anschließen.':['Connect the vehicle.','Branchez le véhicule.','Conecta el vehículo.'],
    'Ladefreigabe wird angefordert …':['Requesting charging access …','Demande d’autorisation de recharge …','Solicitando autorización de carga …'],
    'Startzeit wird gespeichert …':['Saving start time …','Enregistrement de l’heure …','Guardando hora de inicio …'],
    'Ladestart geplant.':['Charging scheduled.','Recharge programmée.','Carga programada.'],
    'Ladefreigabe erteilt.':['Charging enabled.','Recharge autorisée.','Carga habilitada.'],
    'Planung abgebrochen.':['Schedule cancelled.','Programmation annulée.','Programación cancelada.'],
    'Sperrbefehl gesendet.':['Stop command sent.','Commande d’arrêt envoyée.','Orden de parada enviada.'],
    'Warte auf Freigabe':['Waiting for authorization','En attente d’autorisation','Esperando autorización'],
    'Start in {hours} Std. {minutes} Min.':['Starts in {hours} h {minutes} min','Démarrage dans {hours} h {minutes} min','Inicio en {hours} h {minutes} min'],
    'Planung abbrechen':['Cancel schedule','Annuler la programmation','Cancelar programación'],
    'Verbunden':['Connected','Connecté','Conectado'],
    'Kein Fahrzeug':['No vehicle','Aucun véhicule','Sin vehículo'],
    'Unbekannt':['Unknown','Inconnu','Desconocido'],
    'Fahrzeug anschließen':['Connect vehicle','Brancher le véhicule','Conectar vehículo'],
    'Virtuelles Fahrzeug verbunden.':['Virtual vehicle connected.','Véhicule virtuel branché.','Vehículo virtual conectado.'],
    'Virtuelles Fahrzeug getrennt.':['Virtual vehicle disconnected.','Véhicule virtuel débranché.','Vehículo virtual desconectado.'],
    'Gesperrt':['Locked','Verrouillé','Bloqueado'],
    'Bereit':['Ready','Prêt','Listo'],
    'Lädt':['Charging','En recharge','Cargando'],
    'Begrenzt':['Limited','Limité','Limitado'],
    'Fehler':['Error','Erreur','Error'],
    'Geplant':['Scheduled','Programmé','Programado'],
    'Online':['Online','En ligne','En línea'],
    'Offline':['Offline','Hors ligne','Sin conexión'],
    'Webserver nicht erreichbar. Keine aktuellen Messwerte.':['Web server unreachable. No live readings.','Serveur inaccessible. Aucune mesure actuelle.','Servidor web inaccesible. Sin mediciones actuales.'],
    'Leistungsstufe eingestellt.':['Power level set.','Niveau de puissance réglé.','Nivel de potencia ajustado.'],
    'Unbekannter Monat':['Unknown month','Mois inconnu','Mes desconocido'],
    'Aktueller Monat':['Current month','Mois en cours','Mes actual'],
    'Anz. Ladungen':['Sessions','Sessions','Cargas'],
    'Verbrauch':['Consumption','Consommation','Consumo'],
    'Keine Ladungen':['No charging sessions','Aucune recharge','Sin sesiones de carga'],
    'Ladevorgänge':['Charging sessions','Sessions de recharge','Sesiones de carga'],
    'Start':['Start','Début','Inicio'],
    'Ende':['End','Fin','Fin'],
    'Aktiv':['Active','En cours','Activa'],
    'Historie nicht verfügbar.':['History unavailable.','Historique indisponible.','Historial no disponible.'],
    // Statusmeldungen und Validierungsfehler der API.
    'Strompreis eingeben.':['Enter an electricity rate.','Saisissez un tarif.','Introduce una tarifa eléctrica.'],
    'Preis in ct/kWh mit maximal zwei Nachkommastellen eingeben.':['Enter a rate in ct/kWh with at most two decimal places.','Saisissez un tarif en ct/kWh avec deux décimales au maximum.','Introduce el precio en ct/kWh con un máximo de dos decimales.'],
    'Preis zwischen 0 und 1000 ct/kWh eingeben.':['Enter a rate between 0 and 1000 ct/kWh.','Saisissez un tarif entre 0 et 1000 ct/kWh.','Introduce un precio entre 0 y 1000 ct/kWh.'],
    'Kein gültiger Start-Zählerstand':['Invalid initial meter reading','Relevé initial invalide','Lectura inicial del contador no válida'],
    'Kein gültiger End-Zählerstand':['Invalid final meter reading','Relevé final invalide','Lectura final del contador no válida'],
    'Keine gültige Startzeit':['No valid start time','Aucune heure de démarrage valide','No hay hora de inicio válida'],
    'Automatik startet.':['Automatic charging starting.','Démarrage de la recharge automatique.','Iniciando carga automática.'],
    'Automatik übersprungen.':['Automatic charging skipped.','Recharge automatique ignorée.','Carga automática omitida.'],
    'Freigabe unklar – Start abgebrochen.':['Authorization unclear – start cancelled.','Autorisation incertaine – démarrage annulé.','Autorización incierta – inicio cancelado.'],
    'Planung ungültig.':['Invalid schedule.','Programmation invalide.','Programación no válida.'],
    'Planung abgebrochen: Fahrzeug getrennt.':['Schedule cancelled: vehicle disconnected.','Programmation annulée : véhicule débranché.','Programación cancelada: vehículo desconectado.'],
    'Planung abgebrochen: unerwartete Ladung.':['Schedule cancelled: unexpected charging.','Programmation annulée : recharge inattendue.','Programación cancelada: carga inesperada.'],
    'Startzeit verpasst.':['Start time missed.','Heure de démarrage dépassée.','Hora de inicio superada.'],
    'Ladestart fehlgeschlagen.':['Charging could not start.','Échec du démarrage de la recharge.','No se pudo iniciar la carga.'],
    'Ladung freigegeben.':['Charging authorized.','Recharge autorisée.','Carga autorizada.'],
    'Ungültige Personenkonfiguration.':['Invalid people configuration.','Configuration des personnes invalide.','Configuración de personas no válida.'],
    'Bitte einen gültigen Namen eingeben.':['Please enter a valid name.','Veuillez saisir un nom valide.','Introduce un nombre válido.'],
    'Der Name muss 1 bis 80 Zeichen enthalten.':['The name must contain 1 to 80 characters.','Le nom doit comporter de 1 à 80 caractères.','El nombre debe tener entre 1 y 80 caracteres.'],
    'Nur im Demo-Modus verfügbar.':['Available only in demo mode.','Disponible uniquement en mode démo.','Solo disponible en modo demostración.'],
    'Ungültiger Verbindungsstatus.':['Invalid connection status.','État de connexion invalide.','Estado de conexión no válido.'],
    'Ungültige Anfrage.':['Invalid request.','Requête invalide.','Solicitud no válida.'],
    'Eine Person mit diesem Namen existiert bereits.':['A person with this name already exists.','Une personne porte déjà ce nom.','Ya existe una persona con ese nombre.'],
    'Person konnte nicht gespeichert werden.':['Could not save the person.','Impossible d’enregistrer cette personne.','No se pudo guardar la persona.'],
    'Person nicht gefunden.':['Person not found.','Personne introuvable.','Persona no encontrada.'],
    'Person nicht gefunden':['Person not found','Personne introuvable','Persona no encontrada'],
    'Die Person ist einer aktiven Ladung oder Freigabe zugeordnet. Bitte zuerst stoppen.':['This person has an active or authorized charging session. Stop it first.','Cette personne est associée à une recharge active ou autorisée. Arrêtez-la d’abord.','Esta persona tiene una carga activa o autorizada. Deténla primero.'],
    'Für die Person ist eine Ladung geplant. Bitte zuerst die Planung abbrechen.':['A session is scheduled for this person. Cancel the schedule first.','Une recharge est programmée pour cette personne. Annulez-la d’abord.','Hay una carga programada para esta persona. Cancela primero la programación.'],
    'Es gibt eine offene Ladung für diese Person. Bitte zuerst abschließen.':['This person has an open session. Complete it first.','Cette personne a une session ouverte. Terminez-la d’abord.','Esta persona tiene una sesión abierta. Finalízala primero.'],
    'Person konnte nicht gelöscht werden. Bitte erneut prüfen.':['Could not delete the person. Please check again.','Impossible de supprimer cette personne. Veuillez réessayer.','No se pudo eliminar la persona. Compruébalo de nuevo.'],
    'Bild konnte nicht entfernt werden.':['Could not remove the image.','Impossible de supprimer l’image.','No se pudo eliminar la imagen.'],
    'Bitte eine Bilddatei auswählen.':['Please select an image file.','Veuillez choisir un fichier image.','Selecciona un archivo de imagen.'],
    'Nur JPG, PNG und WebP werden unterstützt.':['Only JPG, PNG and WebP are supported.','Seuls JPG, PNG et WebP sont pris en charge.','Solo se admiten JPG, PNG y WebP.'],
    'Bildauflösung zu groß (maximal 25 Megapixel).':['Image resolution too large (max. 25 megapixels).','Résolution trop élevée (25 mégapixels max.).','Resolución demasiado grande (máximo 25 megapíxeles).'],
    'Ungültiges oder zu großes Bild.':['Invalid or oversized image.','Image invalide ou trop volumineuse.','Imagen no válida o demasiado grande.'],
    'Bild konnte nicht gespeichert werden.':['Could not save the image.','Impossible d’enregistrer l’image.','No se pudo guardar la imagen.'],
    'Ladung aktiv oder geplant.':['Charging active or scheduled.','Recharge active ou programmée.','Carga activa o programada.'],
    'Uhrzeit oder Modus ungültig.':['Invalid time or mode.','Heure ou mode invalide.','Hora o modo no válido.'],
    'Standardperson wählen.':['Select a default person.','Choisissez une personne par défaut.','Selecciona una persona predeterminada.'],
    'Ladestart nicht mehr verfügbar. Bitte Ansicht aktualisieren.':["Charging start is no longer available. Please refresh the page.","Ce démarrage n’est plus disponible. Veuillez actualiser la page.","El inicio de carga ya no está disponible. Actualiza la página."],
    'Ungültige Startzeit.':['Invalid start time.','Heure de démarrage invalide.','Hora de inicio no válida.'],
    'Startzeit erneut wählen.':['Select the start time again.','Choisissez à nouveau l’heure.','Selecciona de nuevo la hora de inicio.'],
    'Fahrzeug anschließen und Wallbox sperren.':['Connect the vehicle and lock the wallbox.','Branchez le véhicule et verrouillez la borne.','Conecta el vehículo y bloquea el cargador.'],
    'Planung fehlgeschlagen.':['Scheduling failed.','Échec de la programmation.','Error al programar.'],
    'Ungültiger Startmodus.':['Invalid start mode.','Mode de démarrage invalide.','Modo de inicio no válido.'],
    'Wallbox nicht gesperrt.':['Wallbox is not locked.','La borne n’est pas verrouillée.','El cargador no está bloqueado.'],
    'Leistung kann nur während aktivem Laden geändert werden':['Power can only be adjusted while charging','La puissance ne peut être réglée que pendant la recharge','La potencia solo se puede ajustar durante la carga'],
    'Ungültige Leistungsstufe':['Invalid power level','Niveau de puissance invalide','Nivel de potencia no válido'],
    'Fehler beim Setzen der Ladeleistung:':['Could not set charging power:','Impossible de régler la puissance :','No se pudo ajustar la potencia:'],
    'Schreiben Register {address} fehlgeschlagen':['Writing register {address} failed','Échec de l’écriture du registre {address}','Error al escribir el registro {address}'],
    'Verbindung zur Wallbox fehlgeschlagen':['Connection to wallbox failed','Échec de connexion à la borne','Error de conexión al cargador'],
    'Ungültiger virtueller Steuerbefehl':['Invalid virtual control command','Commande virtuelle invalide','Orden de control virtual no válida']
  };
  const languages = {de:'de-DE',en:'en-GB',fr:'fr-FR',es:'es-ES'};
  const indices = {en:0,fr:1,es:2};
  const supported = value => Object.hasOwn(languages,value);
  let saved;
  try { saved=localStorage.getItem('wallbox.language'); } catch {}
  const pageUrl=new URL(location.href);
  const selected=pageUrl.searchParams.get('lang');
  const language=supported(selected)?selected:supported(saved)?saved:'de';
  const locale=languages[language];
  try { localStorage.setItem('wallbox.language',language); } catch {}
  const t=(source,params={})=>{
    if(typeof source!=='string')return source;
    const key=source.trim();
    if(!key)return source;
    const translation=language==='de'||!Object.hasOwn(texts,key)?key:texts[key][indices[language]];
    const value=translation.replace(/\{(\w+)\}/g,(all,name)=>Object.hasOwn(params,name)?String(params[name]):all);
    return source.match(/^\s*/)[0]+value+source.match(/\s*$/)[0];
  };
  function apiError(source) {
    if(typeof source!=='string'||!source)return t('Anfrage fehlgeschlagen');
    const match=source.match(/^Schreiben Register (\d+) fehlgeschlagen$/);
    if(match)return t('Schreiben Register {address} fehlgeschlagen',{address:match[1]});
    const prefix='Fehler beim Setzen der Ladeleistung:';
    if(source.startsWith(prefix))return t(prefix)+' '+apiError(source.slice(prefix.length).trim());
    if(Object.hasOwn(texts,source.trim())||language==='de')return t(source);
    if(source.includes('Verbindung zur Wallbox fehlgeschlagen'))return t('Verbindung zur Wallbox fehlgeschlagen');
    return t('Anfrage fehlgeschlagen');
  }
  function formatSchedule(due){
    if(due==null||!Number.isFinite(Number(due)))return '—';
    return new Intl.DateTimeFormat(locale,{day:'2-digit',month:'2-digit',year:'numeric',hour:'2-digit',minute:'2-digit',hourCycle:'h23',timeZone:'Europe/Berlin',timeZoneName:'short'}).format(new Date(Number(due)*1000));
  }
  function translatePage(){
    document.documentElement.lang=language;
    const walker=document.createTreeWalker(document.body,NodeFilter.SHOW_TEXT);
    let node;
    while((node=walker.nextNode())){
      const key=node.nodeValue.trim();
      if(Object.hasOwn(texts,key))node.nodeValue=t(node.nodeValue);
    }
    document.querySelectorAll('[aria-label],[alt],[placeholder]').forEach(element=>{
      ['aria-label','alt','placeholder'].forEach(attr=>{
        const value=element.getAttribute(attr);
        if(value&&Object.hasOwn(texts,value.trim()))element.setAttribute(attr,t(value));
      });
    });
    const selector=document.getElementById('languageSelect');
    if(selector)selector.value=language;
  }
  // Nur die Einstellungsauswahl wird nach dem lokalen Neuladen wieder geöffnet.
  const resumeTab=pageUrl.searchParams.get('settings');
  if(resumeTab){
    pageUrl.searchParams.delete('settings');
    history.replaceState(null,'',pageUrl);
  }
  function changeLanguage(next,tab){
    if(!supported(next)||next===language)return;
    try{localStorage.setItem('wallbox.language',next);}catch{}
    const url=new URL(location.href);
    url.searchParams.set('lang',next);
    url.searchParams.set('settings',tab);
    location.assign(url.toString());
  }
  translatePage();
  return {t,apiError,language,locale,formatSchedule,resumeTab,changeLanguage};
})();
