import QtQuick

Item {
    id: root
    property string sourceUrl: Theme.bannerUrl
    visible: sourceUrl.length > 0
    height: visible ? Math.min(180, width * 0.32) : 0

    ElevatedCard {
        anchors.fill: parent

        Image {
            anchors.fill: parent
            source: root.sourceUrl
            fillMode: Image.PreserveAspectCrop
            asynchronous: true
            cache: true
        }
    }
}
