import QtQuick
import "../components"

Item {
    ErrorState {
        anchors.centerIn: parent
        width: parent.width
        message: App.fatalReason.length ? App.fatalReason : "Configuration error"
    }
}
